# 利用方法

[English version](usage.md)

このガイドでは、対象にするリポジトリの選び方、Dev Container の起動方法、
公開したリポジトリのプロジェクト設定を変更せずにツールを使う方法を説明
します。

## 目次

- [リポジトリへのアクセスを設定する](#リポジトリへのアクセスを設定する)
  - [ホスト側のソースパス](#ホスト側のソースパス)
  - [コンテナ側のマウント先](#コンテナ側のマウント先)
- [allowlist の変更を反映する](#allowlist-の変更を反映する)
- [実行時のバージョン](#実行時のバージョン)
- [エージェントと認証情報](#エージェントと認証情報)
- [Docker と Compose](#docker-と-compose)
- [内部コンテナの DNS](#内部コンテナの-dns)
- [トラブルシューティング](#トラブルシューティング)

## リポジトリへのアクセスを設定する

`.devcontainer/allowlist.tsv` に、対象にする追加リポジトリを1行に1件ずつ
記述します。

1列目には、ホスト上に実在する Git リポジトリのルートを示す絶対パスを指定します。
2列は1つのリテラルなタブ文字（`U+0009`）で区切り、`<TAB>` という文字列や
スペースは使いません。

標準構成では、`dev_sandbox` リポジトリ自身は現在の workspace であるため、
allowlist に登録する必要はありません。エージェントにアクセスさせたい追加
リポジトリだけを登録してください。

Dev Containers クライアントは、生成された allowlist のマウントとは別に、現在
のリポジトリを `workspace` サービスへマウントします。`@workspace` は現在の
リポジトリを allowlist による生成マウントへ追加するための特殊な source 指定
であり、通常の workspace 利用に必須ではありません。現在のリポジトリも
`docker` サービスへマウントしたい場合や、Compose の build source・bind source
に明示的な宛先が必要な場合は、`@workspace` の行を追加してください。

### ホスト側のソースパス

追加リポジトリには、存在する Git リポジトリのルートを指定してください。
複数のリポジトリを含む広い親ディレクトリは指定しないでください。ホスト側
のパスは絶対パスである必要があります。次の source 形式を使えます。

- `@workspace` — 現在のリポジトリの絶対パスに解決されます。
- `@workspace:/absolute/path/to/repository` — 明示した絶対パスを source として指定します。現在のリポジトリに限定されません。
- `@workspace-relative:../org/repo` — 現在のリポジトリからの相対パスを指定します。

パスは Compose の起動前にホスト上で解決・検証されます。存在しないパス、
Git リポジトリでないパス、入れ子になったパス、重複するパスは、安全側に
倒して拒否されます。

### コンテナ側のマウント先

2列目は必須で、コンテナ内の正規化された絶対ディレクトリパスを指定します。
ファイルシステムのルート `/` と `/workspaces` 自体は予約されており、末尾の `/` は
使えません。マウント先は重複できず、別のマウント先の内側にもできません。同じマウント先
が `workspace` サービスと `docker` サービスの両方で使われるため、リポジトリ
をホスト上の既存の場所に置いたまま、両方のコンテナ内で整理された構成に
できます。

設定したマウント先が、`workspace` と `docker` の両サービスにおける canonical な
リポジトリパスになります。移動用 alias や追加のシンボリックリンクは作成しません。
`/workspaces` 配下にネストした宛先を指定した場合、不足する親ディレクトリは
`dev:dev` 所有の一時的な `tmpfs` として用意されます。この仮想的な親ディレクトリ
によって、ホスト側の親ディレクトリ全体が公開されることはありません。

サービスが所有する固定マウントとも重ならない宛先を指定する必要があります。
固定マウント自身、その配下、または固定マウントの親になる宛先は拒否されます。
現在予約されている固定パスは、`/docker-socket`、`/tmp`、
`/home/dev/.cache/mise`、`/home/dev/.local/share/mise`、
`/home/dev/.local/share/docker`、`/home/dev/.codex`、`/home/dev/.claude`、
`/run/ssh-agent` です。最後のパスは、任意の SSH agent 転送を無効にしている
場合でも、後から中継を有効にできるため予約されます。`/workspaces` 配下の宛先は
引き続き使用できます。予約されるのは `/workspaces` 自体だけです。

Dev Containers クライアントを実行するホストには `python3` が必要です。
allowlist の準備処理は Python の標準ライブラリだけを使い、サードパーティー
パッケージを必要としません。

## allowlist の変更を反映する

`.devcontainer/allowlist.tsv` を変更したら、Dev Container に接続した
ターミナルではなく、リポジトリのルートにいるホスト側のターミナルで
次のコマンドを実行して変更を反映します。

```sh
bash .devcontainer/prepare-mounts
```

このコマンドが失敗した場合は、allowlist を修正して再実行してください。以前の生成設定の
まま Dev Container を再開・再作成してはいけません。成功した後、追加・削除を反映するために
コンテナを再作成します。

- CLI: `devcontainer up --workspace-folder . --remove-existing-container`
- VS Code: `Dev Containers: Rebuild Container` を実行
- Zed: リモートプロジェクトを閉じ、ホスト側で上記の CLI コマンドを実行してから、
  `Project: Open Remote` で再度開く

Dev Containers クライアントは起動時の `initializeCommand` からもこのコマンドを実行しますが、
マウントポリシーを変更した場合に明示的なコンテナ再作成を省略することはできません。この処理は
`.devcontainer/compose.allowlist.local.yml` を再生成しますが、これは Git の対象外であり、
コミットしたり手で編集したりしないでください。allowlist だけを変更した場合、イメージの再ビルドは
不要です。イメージや Compose 設定を変更した場合は、利用するクライアントが提供する再ビルド手順を
使ってください。Dev Containers CLI のオプションは `devcontainer up --help` で確認できます。

Docker Desktop では、新しく追加するリポジトリごとに、コンテナを再作成する前に File Sharing の
許可を追加してください。複数のリポジトリを含む広い親ディレクトリは共有しないでください。

再接続後は、workspace のターミナルから設定した宛先が存在することを確認してください。CLI では
例えば次のように確認できます。

```sh
devcontainer exec --workspace-folder . ls -ld /workspaces/api
```

`/workspaces/api` は2列目に設定した完全な宛先（先頭のパス要素を含む）へ置き換えてください。
`/workspaces` 外の宛先も、設定した絶対パスをそのまま使って確認します。allowlist から削除した
宛先が残っていないことも確認してください。

## 実行時のバージョン

イメージのビルド時に最新の安定版 `mise` をインストールし、
`.devcontainer/mise.toml` をイメージレベルのツールマニフェストとして使います。
イメージには、最新の Node.js LTS、Codex、Claude Code、および同ファイルに記載
された基本的なコマンドラインツールが含まれます。`latest` を使うエントリは
イメージのビルド時に解決されるため、新しいバージョンを取得するには Dev
Container を再ビルドしてください。

インストールしたツールは Docker が管理する名前付きボリューム
`mise-data` に保存され、ダウンロードキャッシュは別の `mise-cache` ボリューム
に保存されます。どちらもこのリポジトリには保存されません。空の `mise-data`
ボリュームはイメージに含まれるツールから初期化されますが、既存のボリューム
はイメージを再ビルドしても上書きされません。

プロジェクトのツールバージョンと `mise` の設定は、それぞれの公開した
リポジトリが管理します。Dev Container がプロジェクト設定を自動的に調査、
インストール、変換することはありません。例えば、各リポジトリの通常の
ワークフローを使ってください。

```bash
mise trust
mise install
mise current
```

シェルは `mise` 標準の Bash activation を読み込むため、そのリポジトリで作業
すると、信頼済みのプロジェクト設定が適用されます。イメージを再ビルドした後
にインストール済みのツールを更新したい場合は、`mise upgrade` を明示的に
実行してください。

## エージェントと認証情報

イメージには `mise` 経由で Codex と Claude Code がインストールされます。
認証情報やその他の変更されるエージェント状態は、リポジトリではなく名前付き
ボリュームに保存されます。本プロジェクトは `.codex/config.toml` や
`.claude/settings.json` をコミットせず、ランチャーでユーザー設定を上書き
することもありません。`codex` や `claude` は通常どおり起動し、設定はユーザー
自身が管理してください。

プライベートな Git 依存関係が必要なビルドでは、ホストの SSH agent に最小限の
権限を持つ開発用キーを読み込み、`SSH_AUTH_SOCK` を設定した状態で Dev Container
を起動または再開してください。起動スクリプトは、その Unix socket だけを専用
の中継サービス経由で `workspace` サービスに転送します。`~/.ssh` をマウント
したり、socket を `docker` サービスへ転送したりすることはありません。
`ssh-add -l` で読み込まれた identity を確認し、本番用または関係のないキーを
含む agent を転送しないでください。SSH agent の socket を変更した場合は、
Dev Container を再開または再ビルドする必要があります。

## Docker と Compose

Docker コマンドは、専用の `docker` サービスで動作する rootless デーモンを
使います。データディレクトリと Unix socket は名前付きボリュームです。socket
は RootlessKit の `/run` における private な copy-up namespace の外側にある
`/docker-socket/docker.sock` にマウントされます。外側の Docker Desktop や
Linux Docker Engine の socket が workspace にマウントされることはありません。

workspace の Docker CLI は、クライアント設定ディレクトリとして
`/home/dev/.config/docker-cli` を使います。プライベートレジストリで明示的な
認証が必要な場合は、Dev Container 内で `docker login` を実行してください。
認証情報は内部 Docker CLI の設定に保存されます。

リポジトリは、設定したコンテナ内パスに `workspace` と `docker` の両サービスで
マウントされます。内部 Docker デーモンは自身の mount namespace から bind
source を解決するため、既存の Compose ファイルで相対パスの bind mount を使う
場合も、同じ設定済みパスから解決される必要があります。リポジトリの Compose
ワークフローは、そのパスから実行してください。

## 内部コンテナの DNS

rootless デーモンは、内部デーモンが作成したコンテナへ利用可能な上流 DNS
サーバーを渡します。ホスト側の `prepare-mounts` は、macOS では `scutil --dns`、
Linux では `/etc/resolv.conf` から、プラットフォームの resolver 設定を使って
DNS サーバーを検出します。Linux が systemd-resolved を使っている場合は、
`/run/systemd/resolve/resolv.conf` の上流設定を読み取り、それでも見つからない
場合に任意の `resolvectl dns` fallback を試します。loopback や stub resolver の
アドレスは、内部コンテナの namespace から到達できないため転送されません。
また、unspecified、multicast、link-local、reserved のアドレスも除外します。
ホスト側の検出だけでは、Docker の Linux VM や内部 namespace から resolver に
到達できることまでは証明できないため、ネットワーク到達性が重要な場合は実行時
の DNS lookup も必要です。

`docker` サービスはホストの DNS 検出を繰り返しません。`prepare-mounts` が検証
して生成した値を必要とし、ベース Compose からホストの環境変数を直接渡すことは
ありません。自動検出が十分でない場合は、Docker の Linux VM から到達できる
resolver アドレスをカンマ区切りで `ROOTLESS_DOCKER_DNS` に設定し、Dev Container
を再開してください。

```bash
export ROOTLESS_DOCKER_DNS=<reachable-dns-server>
```

loopback アドレスや Docker の組み込み resolver アドレスは使わないでください。
macOS では Finder や Dock から起動した Zed が、シェルの環境変数を引き継がない
ことがあります。自動検出を使うか、環境変数を設定したシェルからプロジェクト
を起動してください。

## トラブルシューティング

- rootless デーモンが起動しない場合は、`docker compose logs docker` を確認して
  ください。上流 DNS がないというメッセージは、ホスト側の検出で利用可能な
  アドレスが見つからなかったことを示します。`ROOTLESS_DOCKER_DNS` を設定し、
  Dev Container を再開してください。
- 内部 build で `Temporary failure resolving` が発生した場合は、`docker` サービス
  のログで選択された DNS サーバーを確認してください。自動検出で到達可能な
  resolver が見つからない場合は、環境変数を設定します。
- 内部コンテナが session-keyring エラーで起動前に失敗する場合は、
  `NoNewKeyring` の runtime 設定がインストールされるようにイメージを再ビルド
  してください。ホスト全体の kernel quota を増やして回避しないでください。
- macOS では、Docker Desktop の File Sharing を広いホームディレクトリの親では
  なく、現在のリポジトリと allowlist に登録した各リポジトリに設定してください。
- Git メタデータがないリポジトリは allowlist に追加できません。
- bind source が設定したコンテナ内パスに見えない場合は、リポジトリ側の Docker
  ワークフローを調整してください。回避策として広いホスト側の親ディレクトリを
  マウントしないでください。
