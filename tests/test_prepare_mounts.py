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

    def run(
        self,
        command: Sequence[str],
        *,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        return subprocess.CompletedProcess(command, 0, self.stdout, "")


class ResolverCommandRunner:
    """Return command-specific resolver output without invoking host commands."""

    def __init__(
        self, responses: dict[tuple[str, ...], subprocess.CompletedProcess[str]]
    ):
        self.responses = responses
        self.commands: list[Sequence[str]] = []

    def run(
        self,
        command: Sequence[str],
        *,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        return self.responses.get(
            tuple(command),
            subprocess.CompletedProcess(command, 127, "", "command not found"),
        )


class TimeoutResolverCommandRunner:
    """Raise a subprocess timeout for resolver command handling tests."""

    def __init__(self) -> None:
        self.commands: list[Sequence[str]] = []

    def run(
        self,
        command: Sequence[str],
        *,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        raise subprocess.TimeoutExpired(command, timeout)


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

    def write(
        self,
        override: Path,
        override_content: str,
    ) -> None:
        self.override_content = override_content


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
                "@workspace\t\t\t/workspaces/repo-alpha\n",
                encoding="utf-8",
            )

            repositories = prepare_mounts.AllowlistValidator(
                FakeCommandRunner("")
            ).parse(allowlist, root)

            self.assertEqual(len(repositories), 1)
            self.assertEqual(repositories[0].source, root.resolve())
            self.assertEqual(str(repositories[0].target), "/workspaces/repo-alpha")

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

    def test_same_basename_targets_are_allowed(self) -> None:
        """Mount destinations with the same basename do not need aliases."""

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

            repositories = prepare_mounts.AllowlistValidator(
                FakeCommandRunner(f"{external}\n")
            ).parse(allowlist, root)

            self.assertEqual(len(repositories), 2)

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
                        "@workspace\t/workspaces/repo-alpha",
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
                    f"{source_spec}\t/workspaces/repo-alpha\n",
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
                        f"{root}\t/workspaces/repo-alpha",
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
                ["/workspaces/repo-alpha", "/workspaces/external"],
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
            Path("/host/sandbox"),
            None,
        )

        self.assertEqual(rendered.count("target: '/workspaces/example'"), 2)
        self.assertNotIn("tmpfs:", rendered)
        self.assertNotIn("ROOTLESS_DOCKER_DNS", rendered)

    def test_renderer_adds_deduplicated_workspace_parent_tmpfs_mounts(self) -> None:
        repositories = [
            prepare_mounts.AllowlistedRepository(
                source=Path("/host/repo-alpha"),
                target="/workspaces/group-alpha/repo-alpha",
            ),
            prepare_mounts.AllowlistedRepository(
                source=Path("/host/repo-beta"),
                target="/workspaces/group-alpha/repo-beta",
            ),
            prepare_mounts.AllowlistedRepository(
                source=Path("/host/deep"),
                target="/workspaces/group-beta/service/repo-gamma",
            ),
        ]

        rendered = prepare_mounts.ComposeOverrideRenderer().render(
            repositories,
            Path("/host/sandbox"),
            None,
        )

        for parent in (
            "/workspaces/group-alpha",
            "/workspaces/group-beta",
            "/workspaces/group-beta/service",
        ):
            mount = f"'{parent}:uid=1000,gid=1000,mode=0755'"
            self.assertEqual(rendered.count(mount), 2)
        self.assertEqual(
            rendered.count("target: '/workspaces/group-alpha/repo-alpha'"),
            2,
        )
        self.assertNotIn("allowlist.local.tsv", rendered)
        self.assertNotIn("/run/devcontainer/allowlist.tsv", rendered)

    def test_renderer_removes_stale_ssh_relay_socket(self) -> None:
        """The relay must recover when its named volume contains an old socket."""

        repository = prepare_mounts.AllowlistedRepository(
            source=Path("/host/example"),
            target="/workspaces/example",
        )

        rendered = prepare_mounts.ComposeOverrideRenderer().render(
            [repository],
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
        self.assertEqual(tuple(map(str, outer.target.workspace_parent_paths)), ())
        self.assertEqual(
            tuple(map(str, nested.target.workspace_parent_paths)),
            ("/workspaces/repository",),
        )
        outside = prepare_mounts.ContainerMountPath.parse("/other/workspaces/repository")
        self.assertEqual(tuple(map(str, outside.workspace_parent_paths)), ())

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
        self.assertTrue(outer.conflicts_with(outer))
        self.assertTrue(nested.conflicts_with(outer))
        self.assertTrue(outer.conflicts_with(nested))
        self.assertFalse(
            outer.conflicts_with(
                prepare_mounts.ContainerMountPath.parse("/workspaces/other")
            )
        )
        with self.assertRaisesRegex(
            prepare_mounts.AllowlistError,
            "reserved for the workspace root",
        ):
            prepare_mounts.ContainerMountPath.parse("/workspaces")

    def test_allowlist_rejects_exact_fixed_mount_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repo-alpha"
            root.mkdir()
            allowlist = root / "allowlist.tsv"
            allowlist.write_text(
                "@workspace\t/tmp\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                prepare_mounts.AllowlistError,
                r"container destination /tmp conflicts with fixed mount path /tmp",
            ) as error:
                prepare_mounts.AllowlistValidator(FakeCommandRunner("")).parse(
                    allowlist,
                    root,
                )

            self.assertNotIn(str(root), str(error.exception))

    def test_allowlist_rejects_destination_nested_under_fixed_mount(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repo-alpha"
            root.mkdir()
            allowlist = root / "allowlist.tsv"
            allowlist.write_text(
                "@workspace\t/home/dev/.codex/project\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                prepare_mounts.AllowlistError,
                "container destination /home/dev/.codex/project conflicts with "
                "fixed mount path /home/dev/.codex",
            ):
                prepare_mounts.AllowlistValidator(FakeCommandRunner("")).parse(
                    allowlist,
                    root,
                )

    def test_allowlist_rejects_destination_parent_of_fixed_mount(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repo-alpha"
            root.mkdir()
            allowlist = root / "allowlist.tsv"
            allowlist.write_text(
                "@workspace\t/home/dev/.local/share\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                prepare_mounts.AllowlistError,
                "container destination /home/dev/.local/share conflicts with "
                "fixed mount path /home/dev/.local/share/mise",
            ):
                prepare_mounts.AllowlistValidator(FakeCommandRunner("")).parse(
                    allowlist,
                    root,
                )

    def test_allowlist_rejects_destination_under_optional_ssh_relay_mount(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repo-alpha"
            root.mkdir()
            allowlist = root / "allowlist.tsv"
            allowlist.write_text(
                "@workspace\t/run/ssh-agent/project\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                prepare_mounts.AllowlistError,
                "container destination /run/ssh-agent/project conflicts with "
                "fixed mount path /run/ssh-agent",
            ):
                prepare_mounts.AllowlistValidator(FakeCommandRunner("")).parse(
                    allowlist,
                    root,
                )

    def test_allowlist_allows_workspaces_descendants(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repo-alpha"
            root.mkdir()
            allowlist = root / "allowlist.tsv"
            allowlist.write_text(
                "@workspace\t/workspaces/repo-alpha\n",
                encoding="utf-8",
            )

            repositories = prepare_mounts.AllowlistValidator(
                FakeCommandRunner("")
            ).parse(allowlist, root)

            self.assertEqual(str(repositories[0].target), "/workspaces/repo-alpha")

    def test_dns_servers_are_immutable_and_renderable(self) -> None:
        servers = prepare_mounts.DnsServers.from_detected(
            ["2001:db8::53", "192.0.2.53", "192.0.2.53"]
        )

        self.assertIsNotNone(servers)
        assert servers is not None
        self.assertEqual(tuple(servers), ("192.0.2.53", "2001:db8::53"))
        self.assertEqual(servers.as_environment_value(), "192.0.2.53,2001:db8::53")

    def test_dns_servers_reject_reserved_addresses(self) -> None:
        for address in ("255.255.255.255", "240.0.0.1", "::ffff:255.255.255.255"):
            self.assertIsNone(prepare_mounts.DnsServers.from_detected([address]))
            with self.assertRaisesRegex(
                prepare_mounts.AllowlistError,
                "unusable IP address",
            ):
                prepare_mounts.DnsServers.from_explicit(address)

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
                systemd_resolv_conf_path=Path("/nonexistent/systemd-resolv.conf"),
            )

            servers = detector.detect(None)
            self.assertIsNotNone(servers)
            assert servers is not None
            self.assertEqual(tuple(servers), ("192.0.2.53", "2001:db8::53"))
            self.assertEqual(runner.commands, [["resolvectl", "dns"]])

    def test_linux_resolver_timeout_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            resolv_conf = Path(temporary_directory) / "resolv.conf"
            resolv_conf.write_text("nameserver 127.0.0.53\n", encoding="utf-8")
            runner = TimeoutResolverCommandRunner()
            detector = prepare_mounts.HostResolverDetector(
                runner,
                platform_name="linux",
                resolv_conf_path=resolv_conf,
                systemd_resolv_conf_path=Path("/nonexistent/systemd-resolv.conf"),
            )

            self.assertIsNone(detector.detect(None))
            self.assertEqual(runner.commands, [["resolvectl", "dns"]])

    def test_linux_uses_systemd_resolved_upstream_file_before_resolvectl(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            resolv_conf = Path(temporary_directory) / "stub-resolv.conf"
            systemd_resolv_conf = Path(temporary_directory) / "resolv.conf"
            resolv_conf.write_text(
                "nameserver 127.0.0.53\n",
                encoding="utf-8",
            )
            systemd_resolv_conf.write_text(
                "nameserver 10.0.0.53\nnameserver 2001:db8::53\n",
                encoding="utf-8",
            )
            runner = ResolverCommandRunner({})
            detector = prepare_mounts.HostResolverDetector(
                runner,
                platform_name="linux",
                resolv_conf_path=resolv_conf,
                systemd_resolv_conf_path=systemd_resolv_conf,
            )

            servers = detector.detect(None)

            self.assertIsNotNone(servers)
            assert servers is not None
            self.assertEqual(tuple(servers), ("10.0.0.53", "2001:db8::53"))
            self.assertEqual(runner.commands, [])

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
                systemd_resolv_conf_path=Path("/nonexistent/systemd-resolv.conf"),
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
            )
            paths.allowlist.write_text(
                "@workspace\t/workspaces/repo-alpha\n",
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
            )
            paths.allowlist.write_text(
                "@workspace\t/workspaces/repo-alpha\n",
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
