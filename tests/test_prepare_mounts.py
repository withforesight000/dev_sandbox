"""Unit tests for the host-side prepare-mounts application service."""

from __future__ import annotations

import io
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Sequence
from pathlib import Path

DEVCONTAINER_PATH = Path(__file__).resolve().parents[1] / ".devcontainer"
sys.path.insert(0, str(DEVCONTAINER_PATH))
import prepare_mounts


class FakeCommandRunner:
    """Return a controlled Git root without invoking the host Git command."""

    def __init__(self, stdout: str) -> None:
        self.stdout = stdout
        self.commands: list[Sequence[str]] = []

    def run(self, command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        return subprocess.CompletedProcess(command, 0, self.stdout, "")


class ResolverCommandRunner:
    """Return command-specific resolver output without invoking host commands."""

    def __init__(
        self, responses: dict[tuple[str, ...], subprocess.CompletedProcess[str]]
    ):
        self.responses = responses
        self.commands: list[Sequence[str]] = []

    def run(self, command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        return self.responses.get(
            tuple(command),
            subprocess.CompletedProcess(command, 127, "", "command not found"),
        )


class FakeResolverDetector:
    """Return controlled DNS servers to test PrepareMounts orchestration."""

    def __init__(self, dns_servers: list[str] | None):
        self.dns_servers = (
            prepare_mounts.DnsServers.from_detected(dns_servers)
            if dns_servers is not None
            else None
        )
        self.explicit_overrides: list[str | None] = []

    def detect(
        self,
        explicit_override: str | None,
    ) -> prepare_mounts.DnsServers | None:
        self.explicit_overrides.append(explicit_override)
        return self.dns_servers


class MemoryFileWriter:
    """Capture generated file contents for application-service assertions."""

    def __init__(self) -> None:
        self.override_content = ""
        self.aliases_content = ""

    def write(
        self,
        override: Path,
        aliases: Path,
        override_content: str,
        aliases_content: str,
    ) -> None:
        self.override_content = override_content
        self.aliases_content = aliases_content


class PrepareMountsTests(unittest.TestCase):
    """Verify validation and orchestration independently of host side effects."""

    def test_legacy_three_column_row_with_name_is_rejected(self) -> None:
        """The input format no longer accepts a separate repository name."""

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "sandbox"
            root.mkdir()
            allowlist = root / "allowlist.tsv"
            allowlist.write_text(
                "legacy-name\t@workspace\t/workspaces/legacy-name\n",
                encoding="utf-8",
            )

            validator = prepare_mounts.AllowlistValidator(FakeCommandRunner(""))
            with self.assertRaisesRegex(
                prepare_mounts.AllowlistError,
                "exactly two tab-separated fields",
            ):
                validator.parse(allowlist, root)

    def test_repeated_tabs_between_columns_are_accepted(self) -> None:
        """Treat repeated tabs as one separator without allowing missing columns."""

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "sandbox"
            root.mkdir()
            root = root.resolve()
            allowlist = root / "allowlist.tsv"
            allowlist.write_text(
                "@workspace\t\t\t/workspaces/dev-sandbox\n",
                encoding="utf-8",
            )

            repositories = prepare_mounts.AllowlistValidator(
                FakeCommandRunner("")
            ).parse(allowlist, root)

            self.assertEqual(len(repositories), 1)
            self.assertEqual(repositories[0].source, root.resolve())
            self.assertEqual(str(repositories[0].target), "/workspaces/dev-sandbox")
            self.assertEqual(repositories[0].workspace_alias, "dev-sandbox")

    def test_allowlist_does_not_require_the_sandbox_repository(self) -> None:
        """Allow mounting only explicitly selected repositories."""

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "sandbox"
            external = Path(temporary_directory) / "external"
            root.mkdir()
            external.mkdir()
            root = root.resolve()
            external = external.resolve()
            allowlist = root / "allowlist.tsv"
            allowlist.write_text(
                f"{external}\t/workspaces/external\n",
                encoding="utf-8",
            )

            repositories = prepare_mounts.AllowlistValidator(
                FakeCommandRunner(f"{external}\n")
            ).parse(allowlist, root)

            self.assertEqual(len(repositories), 1)
            self.assertEqual(repositories[0].source, external)
            self.assertEqual(str(repositories[0].target), "/workspaces/external")

    def test_duplicate_workspace_aliases_are_rejected(self) -> None:
        """Mount destinations with the same basename cannot share an alias."""

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "sandbox"
            external = Path(temporary_directory) / "external"
            root.mkdir()
            external.mkdir()
            root = root.resolve()
            external = external.resolve()
            allowlist = root / "allowlist.tsv"
            allowlist.write_text(
                "\n".join(
                    [
                        "@workspace\t/workspaces/project",
                        f"{external}\t/other/project",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                prepare_mounts.AllowlistError,
                "duplicate workspace alias: project",
            ):
                prepare_mounts.AllowlistValidator(
                    FakeCommandRunner(f"{external}\n")
                ).parse(allowlist, root)

    def test_workspace_absolute_source_spec_is_accepted(self) -> None:
        """Resolve an explicit absolute path introduced by the workspace prefix."""

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "sandbox"
            external = Path(temporary_directory) / "external"
            root.mkdir()
            external.mkdir()
            root = root.resolve()
            external = external.resolve()
            allowlist = root / "allowlist.tsv"
            allowlist.write_text(
                "\n".join(
                    [
                        "@workspace\t/workspaces/dev-sandbox",
                        f"@workspace:{external}\t/workspaces/external",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            repositories = prepare_mounts.AllowlistValidator(
                FakeCommandRunner(f"{external}\n")
            ).parse(allowlist, root)

            self.assertEqual(repositories[1].source, external)

    def test_workspace_absolute_source_spec_requires_absolute_path(self) -> None:
        """Reject an empty or relative value after the absolute-path prefix."""

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "sandbox"
            root.mkdir()
            root = root.resolve()
            validator = prepare_mounts.AllowlistValidator(FakeCommandRunner(""))

            for source_spec in ("@workspace:", "@workspace:relative"):
                allowlist = root / "allowlist.tsv"
                allowlist.write_text(
                    f"{source_spec}\t/workspaces/dev-sandbox\n",
                    encoding="utf-8",
                )

                with self.subTest(source_spec=source_spec), self.assertRaisesRegex(
                    prepare_mounts.AllowlistError,
                    "workspace absolute path must be non-empty and absolute",
                ):
                    validator.parse(allowlist, root)

    def test_git_command_runner_is_injected(self) -> None:
        """Git root validation uses the injected command runner."""

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "sandbox"
            external = Path(temporary_directory) / "external"
            root.mkdir()
            external.mkdir()
            root = root.resolve()
            external = external.resolve()
            allowlist = root / "allowlist.tsv"
            allowlist.write_text(
                "\n".join(
                    [
                        f"{root}\t/workspaces/dev-sandbox",
                        f"{external}\t/workspaces/external",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            runner = FakeCommandRunner(f"{external}\n")

            repositories = prepare_mounts.AllowlistValidator(runner).parse(
                allowlist,
                root,
            )

            self.assertEqual(
                [str(repository.target) for repository in repositories],
                ["/workspaces/dev-sandbox", "/workspaces/external"],
            )
            self.assertEqual(
                runner.commands,
                [["git", "-C", str(external), "rev-parse", "--show-toplevel"]],
            )

    def test_renderer_uses_target_for_both_services(self) -> None:
        """The configured target is emitted for workspace and Docker daemon container."""

        repository = prepare_mounts.AllowlistedRepository(
            source=Path("/host/example"),
            target="/workspaces/example",
        )

        rendered = prepare_mounts.ComposeOverrideRenderer().render(
            [repository],
            Path("/host/allowlist.local.tsv"),
            Path("/host/sandbox"),
            None,
        )

        self.assertEqual(rendered.count("target: '/workspaces/example'"), 2)
        self.assertNotIn("ROOTLESS_DOCKER_DNS", rendered)

    def test_renderer_removes_stale_ssh_relay_socket(self) -> None:
        """The relay must recover when its named volume contains an old socket."""

        repository = prepare_mounts.AllowlistedRepository(
            source=Path("/host/example"),
            target="/workspaces/example",
        )

        rendered = prepare_mounts.ComposeOverrideRenderer().render(
            [repository],
            Path("/host/allowlist.local.tsv"),
            Path("/host/sandbox"),
            Path("/host/ssh-agent.sock"),
        )

        self.assertIn(
            "UNIX-LISTEN:/run/ssh-agent/agent.sock,fork,mode=0666,"
            "unlink-early,unlink-close",
            rendered,
        )

    def test_repository_reports_path_relationships(self) -> None:
        outer = prepare_mounts.AllowlistedRepository(
            source=Path("/host/repository"),
            target="/workspaces/repository",
        )
        nested = prepare_mounts.AllowlistedRepository(
            source=Path("/host/repository/nested"),
            target="/workspaces/repository/nested",
        )
        same = prepare_mounts.AllowlistedRepository(
            source=Path("/host/repository"),
            target="/workspaces/repository",
        )

        self.assertTrue(same.has_same_source_as(outer))
        self.assertTrue(same.has_same_target_as(outer))
        self.assertTrue(nested.is_source_nested_under(outer))
        self.assertTrue(nested.is_target_nested_under(outer))
        self.assertFalse(outer.is_source_nested_under(nested))
        self.assertFalse(outer.is_target_nested_under(nested))

    def test_container_mount_path_validates_and_compares_paths(self) -> None:
        outer = prepare_mounts.ContainerMountPath.parse(
            "/workspaces/repository",
        )
        nested = prepare_mounts.ContainerMountPath.parse(
            "/workspaces/repository/nested",
        )

        self.assertEqual(str(outer), "/workspaces/repository")
        self.assertTrue(nested.is_nested_under(outer))
        self.assertFalse(outer.is_nested_under(nested))
        with self.assertRaisesRegex(
            prepare_mounts.AllowlistError,
            "reserved for workspace aliases",
        ):
            prepare_mounts.ContainerMountPath.parse("/workspaces")

    def test_dns_servers_are_immutable_and_renderable(self) -> None:
        servers = prepare_mounts.DnsServers.from_detected(
            ["2001:db8::53", "192.0.2.53", "192.0.2.53"]
        )

        self.assertIsNotNone(servers)
        assert servers is not None
        self.assertEqual(tuple(servers), ("192.0.2.53", "2001:db8::53"))
        self.assertEqual(servers.as_environment_value(), "192.0.2.53,2001:db8::53")

    def test_scutil_output_is_parsed_and_loopback_servers_are_filtered(self) -> None:
        runner = ResolverCommandRunner(
            {
                ("/usr/sbin/scutil", "--dns"): subprocess.CompletedProcess(
                    ["/usr/sbin/scutil", "--dns"],
                    0,
                    (
                        "nameserver[0] : 127.0.0.11\n"
                        "nameserver[1] : 2001:db8::53\n"
                        "nameserver[2] : 192.0.2.53\n"
                        "nameserver[3] : 192.0.2.53"
                    ),
                    "",
                )
            }
        )
        detector = prepare_mounts.HostResolverDetector(
            runner,
            platform_name="darwin",
            resolv_conf_path=Path("/nonexistent/resolv.conf"),
        )

        servers = detector.detect(None)
        self.assertIsNotNone(servers)
        assert servers is not None
        self.assertEqual(tuple(servers), ("192.0.2.53", "2001:db8::53"))
        self.assertEqual(runner.commands, [["/usr/sbin/scutil", "--dns"]])

    def test_darwin_falls_back_to_host_resolv_conf(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            resolv_conf = Path(temporary_directory) / "resolv.conf"
            resolv_conf.write_text(
                "nameserver 127.0.0.53\nnameserver 198.51.100.53 # VPN\n",
                encoding="utf-8",
            )
            runner = ResolverCommandRunner(
                {
                    ("/usr/sbin/scutil", "--dns"): subprocess.CompletedProcess(
                        ["/usr/sbin/scutil", "--dns"], 1, "", "unavailable"
                    )
                }
            )
            detector = prepare_mounts.HostResolverDetector(
                runner,
                platform_name="darwin",
                resolv_conf_path=resolv_conf,
            )

            servers = detector.detect(None)
            self.assertIsNotNone(servers)
            assert servers is not None
            self.assertEqual(tuple(servers), ("198.51.100.53",))

    def test_linux_uses_resolvectl_when_resolv_conf_only_has_stub(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            resolv_conf = Path(temporary_directory) / "resolv.conf"
            resolv_conf.write_text("nameserver 127.0.0.53\n", encoding="utf-8")
            runner = ResolverCommandRunner(
                {
                    ("resolvectl", "dns"): subprocess.CompletedProcess(
                        ["resolvectl", "dns"],
                        0,
                        "Link 2 (en0)\n    DNS Servers: 192.0.2.53 2001:db8::53\n",
                        "",
                    )
                }
            )
            detector = prepare_mounts.HostResolverDetector(
                runner,
                platform_name="linux",
                resolv_conf_path=resolv_conf,
            )

            servers = detector.detect(None)
            self.assertIsNotNone(servers)
            assert servers is not None
            self.assertEqual(tuple(servers), ("192.0.2.53", "2001:db8::53"))
            self.assertEqual(runner.commands, [["resolvectl", "dns"]])

    def test_no_usable_resolver_returns_none_without_public_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            resolv_conf = Path(temporary_directory) / "resolv.conf"
            resolv_conf.write_text(
                "nameserver 127.0.0.11\nnameserver ::1\n",
                encoding="utf-8",
            )
            runner = ResolverCommandRunner(
                {
                    ("resolvectl", "dns"): subprocess.CompletedProcess(
                        ["resolvectl", "dns"], 1, "", "unavailable"
                    )
                }
            )
            detector = prepare_mounts.HostResolverDetector(
                runner,
                platform_name="linux",
                resolv_conf_path=resolv_conf,
            )

            self.assertIsNone(detector.detect(None))

    def test_explicit_dns_override_takes_precedence(self) -> None:
        runner = ResolverCommandRunner({})
        detector = prepare_mounts.HostResolverDetector(
            runner,
            platform_name="darwin",
            resolv_conf_path=Path("/nonexistent/resolv.conf"),
        )

        servers = detector.detect("192.0.2.53, 2001:db8::53")
        self.assertIsNotNone(servers)
        assert servers is not None
        self.assertEqual(tuple(servers), ("192.0.2.53", "2001:db8::53"))
        self.assertEqual(runner.commands, [])

    def test_invalid_explicit_dns_override_is_rejected(self) -> None:
        detector = prepare_mounts.HostResolverDetector(
            ResolverCommandRunner({}),
            platform_name="darwin",
        )

        with self.assertRaisesRegex(prepare_mounts.AllowlistError, "invalid IP"):
            detector.detect("not-a-dns-server")

    def test_renderer_emits_dns_only_for_docker_daemon_container(self) -> None:
        repository = prepare_mounts.AllowlistedRepository(
            source=Path("/host/example"),
            target="/workspaces/example",
        )

        rendered = prepare_mounts.ComposeOverrideRenderer().render(
            [repository],
            Path("/host/allowlist.local.tsv"),
            Path("/host/sandbox"),
            None,
            prepare_mounts.DnsServers.from_detected(["192.0.2.53", "2001:db8::53"]),
        )

        self.assertIn(
            "ROOTLESS_DOCKER_DNS: '192.0.2.53,2001:db8::53'",
            rendered,
        )
        self.assertEqual(rendered.count("ROOTLESS_DOCKER_DNS"), 1)

    def test_application_injects_file_writer(self) -> None:
        """The application service delegates generated output to its writer."""

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "sandbox"
            root.mkdir()
            root = root.resolve()
            paths = prepare_mounts.PreparationPaths(
                repo_root=root,
                allowlist=root / "allowlist.tsv",
                override=root / "compose.allowlist.local.yml",
                aliases=root / "allowlist.local.tsv",
            )
            paths.allowlist.write_text(
                "@workspace\t/dev-sandbox\n",
                encoding="utf-8",
            )
            writer = MemoryFileWriter()
            output = io.StringIO()
            application = prepare_mounts.PrepareMounts(
                validator=prepare_mounts.AllowlistValidator(FakeCommandRunner("")),
                renderer=prepare_mounts.ComposeOverrideRenderer(),
                writer=writer,
                resolver_detector=FakeResolverDetector(["192.0.2.53"]),
                environment={},
                output=output,
            )

            application.run(paths)

            self.assertEqual(
                writer.aliases_content,
                "dev-sandbox\t/dev-sandbox\n",
            )
            self.assertIn(
                "ROOTLESS_DOCKER_DNS: '192.0.2.53'",
                writer.override_content,
            )
            self.assertIn("validated 1 repository/repositories", output.getvalue())

    def test_application_reports_missing_host_dns_without_public_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "sandbox"
            root.mkdir()
            root = root.resolve()
            paths = prepare_mounts.PreparationPaths(
                repo_root=root,
                allowlist=root / "allowlist.tsv",
                override=root / "compose.allowlist.local.yml",
                aliases=root / "allowlist.local.tsv",
            )
            paths.allowlist.write_text(
                "@workspace\t/dev-sandbox\n",
                encoding="utf-8",
            )
            writer = MemoryFileWriter()
            output = io.StringIO()
            application = prepare_mounts.PrepareMounts(
                validator=prepare_mounts.AllowlistValidator(FakeCommandRunner("")),
                renderer=prepare_mounts.ComposeOverrideRenderer(),
                writer=writer,
                resolver_detector=FakeResolverDetector(None),
                environment={},
                output=output,
            )

            application.run(paths)

            self.assertNotIn("ROOTLESS_DOCKER_DNS", writer.override_content)
            self.assertIn("startup will fail", output.getvalue())


if __name__ == "__main__":
    unittest.main()
