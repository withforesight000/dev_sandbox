# dev_sandbox

[English README](README.md)

> AIエージェントには必要なリポジトリだけを渡し、ホスト全体は渡さない。

`dev_sandbox` は、Codex や Claude などの AI コーディングエージェントが、選択したローカルリポジトリを対象に作業するための Dev Container です。主な目的は、コードの調査・テスト実行・Docker Compose の利用に必要な実用性を保ちながら、関係のないホスト上のデータや機密情報をエージェントに公開しないことです。

現在のリポジトリは `workspace` コンテナにマウントされ、エージェントから利用できます。
追加のリポジトリは allowlist に明示的に登録した場合だけ利用できます。allowlist の
検証に失敗した場合は、安全側に倒して起動を拒否します。通常の構成では、ホストの
ホームディレクトリ、SSH 鍵、クラウド認証情報、Docker 設定、ホストの Docker socket
はコンテナにマウントされません。

## 目次

- [前提条件](#前提条件)
- [クイックスタート](#クイックスタート)
  - [1. リポジトリの allowlist を設定する](#1-リポジトリの-allowlist-を設定する)
  - [2. Dev Container を起動する](#2-dev-container-を起動する)
  - [3. クライアントを選ぶ](#3-クライアントを選ぶ)
- [このリポジトリの目的](#このリポジトリの目的)
- [主な利点](#主な利点)
- [複数リポジトリの横断調査](#複数リポジトリの横断調査)
- [セキュリティ境界](#セキュリティ境界)
- [Docker Sandboxes との比較](#docker-sandboxes-との比較)
- [日常の使い方](#日常の使い方)
- [検証](#検証)
- [ドキュメント](#ドキュメント)
- [ライセンス](#ライセンス)

## 前提条件

- macOS では Docker Desktop、Linux では Docker Engine
- allowlist の生成・検証に使うホスト上の `python3`
- Dev Containers CLI、VS Code、Zed など Dev Container に対応したクライアント
- Docker Desktop を使う場合は、現在のリポジトリと allowlist に登録した各ホストパスを対象にしたファイル共有設定

## クイックスタート

### 1. リポジトリの allowlist を設定する

`.devcontainer/allowlist.tsv` を編集します。各行には、ホスト側の source と
コンテナ側の宛先を、スペースではなく1つのリテラルなタブ文字（`U+0009`）で
区切って記述します。ホスト側の source は、実在する Git リポジトリのルートを
示す絶対パスである必要があります。複数のリポジトリを含む広い親ディレクトリは
指定しないでください。

ホスト側の source は絶対パスで、実在する Git リポジトリのルートである必要があります。複数のリポジトリを含む広い親ディレクトリは指定しないでください。ホスト側の source とコンテナ側の宛先には、重複や入れ子がない必要があります。メインの workspace は allowlist に登録する必要がありません。次の特殊な source 形式も使えます。

```text
@workspace	/workspaces/current
@workspace:/absolute/path/to/repository	/workspaces/explicit
@workspace-relative:../shared-lib	/workspaces/shared-lib
```

`@workspace` は現在のリポジトリを指し、`@workspace:/absolute/path/to/repository` は明示した絶対パスを source として指定します。`@workspace-relative:../shared-lib` は現在のリポジトリを基準に解決されます。解決後のパスも存在し、リポジトリのポリシーを満たしていなければなりません。

コンテナ側の宛先は、正規化された絶対パスである必要があります。`/` と `/workspaces` は予約されており、末尾の `/` は使えません。宛先には重複や入れ子がない必要があります。

### 2. Dev Container を起動する

ホスト側のターミナルを使い、リポジトリのルートから次のコマンドを実行して、ローカルの Compose 設定を生成・検証します。

```sh
bash .devcontainer/prepare-mounts
```

Dev Container クライアントは `initializeCommand` からも `prepare-mounts` を実行します。後から allowlist を更新する場合は、ホスト上で検証し、コンテナを再作成してから再接続します。詳しくは [allowlist の変更を反映する手順](docs/usage.ja.md#allowlist-の変更を反映する) を参照してください。

### 3. クライアントを選ぶ

- CLI: `devcontainer up --workspace-folder .` を実行し、その後 `devcontainer exec --workspace-folder . bash` を使います。
- VS Code: 初回接続では `Dev Containers: Reopen in Container` を実行します。
- Zed: このリポジトリの Dev Container 設定を `Project: Open Remote` で開きます。

`@workspace` の特殊な形式、ネストした宛先、クライアントごとの再作成手順、セキュリティ上の注意は、[利用ガイド](docs/usage.ja.md)を参照してください。

## このリポジトリの目的

AI エージェントは、タスクに必要なコードを調査し、ツールを使い、関連リポジトリを参照できるときに最も役立ちます。しかし、ホスト上の広いディレクトリを渡すと、信頼境界が分かりにくく、監査もしづらくなります。マウントパスを誤ると意図以上の範囲を公開するおそれがあり、リポジトリにはソースコードだけでなく、隠しファイル、ビルドスクリプト、フック、ローカルの認証情報が含まれていることもあります。

本プロジェクトでは、公開するリポジトリの境界を明示し、レビューできるようにしています。

- **追加リポジトリは `.devcontainer/allowlist.tsv` に1行に1件ずつ宣言**します。
- **Dev Container の起動前に `prepare-mounts` でポリシーを検証**します。
- 存在しないパス、リポジトリでないパス、広すぎる親ディレクトリ、入れ子になったマウントや重複するマウント、不正なコンテナ側パスは fail-closed で拒否されます。
- allowlist に登録したリポジトリのパスは `workspace` と、rootless Docker デーモンを実行する専用コンテナ（`docker` サービス）の両方にマウントされるため、相対パスを使う Compose の bind mount も一貫して解決されます。

これにより、エージェント固有のプロジェクト設定を固定せず、標準的な Dev Container ワークフローと、workspace から分離された rootless Docker デーモンを利用できます。設定方法は [利用ガイド](docs/usage.ja.md)、境界と前提条件の詳細は [セキュリティモデル](docs/security-model.ja.md) を参照してください。

## 主な利点

- **タスク単位のアクセス制御** — 現在の調査や変更に必要なリポジトリだけを公開できます。
- **コンテナ内のパスを整理できる** — ホスト上の場所を変えずに、選択した各 Git リポジトリを、コンテナ内の指定した絶対パスへマウントできます。ホスト上で点在しているリポジトリも、コンテナ内では予測しやすい構成にまとめられます。この対応関係は allowlist の一部としてレビュー・検証されます。
- **複数リポジトリの横断調査** — 関連するサービス、クライアント、ライブラリ、スキーマ、インフラを同時に参照し、より根拠のある分析や、変更の影響を判断する際に役立ちます。
- **Dev Container / Compose との互換性** — ホストの Docker socket をエージェントに渡さず、標準的なコンテナツールと、rootless Docker デーモンを実行する専用コンテナを使えます。
- **使い慣れたツール** — `mise`、Codex、Claude、Docker Compose、VS Code、Zed、Dev Containers CLI を通常のワークスペースで利用できます。
- **認証情報の扱いを明示** — SSH agent の転送は opt-in で、workspace にのみ中継されます。ホストの認証情報ファイルはマウントされません。

## 複数リポジトリの横断調査

次のように、複数のリポジトリにまたがる技術的な課題や調査事項は多くあります。

- API リポジトリと、そのクライアントやフロントエンド
- 共通ライブラリと、それを利用するサービス
- スキーマや生成コードと、その生成元・利用先
- アプリケーションリポジトリと、デプロイ・インフラリポジトリ

必要最小限のリポジトリを allowlist に登録すれば、1つのリポジトリのドキュメントだけから推測するのではなく、実際の実装・契約・テストを比較できます。これにより、リポジトリ横断のデバッグ、依存関係の調査、設計レビュー、変更計画において、より根拠のある判断をしやすくなります。

allowlist では、ホスト上のパスとコンテナ内のマウント先を別々に指定できます。そのため、リポジトリをホスト上の既存の場所に置いたまま、Dev Container 内では `/workspaces/api` や `/workspaces/shared-lib` のような整理されたパスで利用できます。これは整理や操作をしやすくするためのものであり、追加のセキュリティ境界ではありません。コンテナ内のパスを変えても、そのリポジトリ内でエージェントがアクセスできる範囲は変わりません。

ただし、これはアクセス範囲に関するトレードオフであり、安全性の保証ではありません。allowlist に登録したリポジトリはすべて `workspace` と `docker` サービスの両方に、読み書き可能な状態でマウントされます。エージェントは隠しファイルやローカル設定を含め、その中のファイルを読み書きできます。リストは最小限に保ち、ポリシーとしてレビューしてください。また、エージェントに扱わせたくない機密情報を含むリポジトリは登録しないでください。

## セキュリティ境界

| リソース | デフォルトの動作 |
| --- | --- |
| workspace（作業用コンテナ） | 現在のプロジェクトをエージェントに公開 |
| 追加リポジトリ | allowlist に明示的に登録した場合のみ利用可能 |
| allowlist 内のリポジトリ | `workspace` と `docker` サービスの両方に、読み書き可能な状態でマウント |
| ホストのホームディレクトリ、SSH 鍵、クラウド認証情報 | マウントされない |
| ホストの Docker 設定と Docker socket | マウントされない。コンテナは専用コンテナ内の rootless Docker デーモンを使用 |
| ホストの SSH agent | `SSH_AUTH_SOCK` を明示的に設定した場合のみ、workspace 専用の中継経由で転送 |
| 外部へのネットワーク通信 | 本リポジトリは、通信を原則拒否する外向き通信ポリシー（deny-by-default）を提供しない。ネットワークアクセスは、別途信頼境界として検討してください |

この構成では、`workspace` は作業用コンテナ、`docker` サービスは rootless Docker デーモンを実行する専用コンテナです。`workspace` コンテナは非特権ユーザーで実行し、capabilities を削減したうえで `no-new-privileges` を設定しています。`docker` サービスは、rootless デーモンの起動に必要な範囲で、外側のコンテナランタイムでは `privileged` として実行されます。これはデプロイ環境における明示的な信頼上の前提です。外側の Docker socket が workspace にマウントされることはありません。

### 保護できるもの

- allowlist に登録していない関係のないホストリポジトリや親ディレクトリ
- 通常の構成におけるホストのホームディレクトリ、SSH 鍵ファイル、クラウド認証情報ファイル、Docker 設定、外側の Docker socket
- 存在しない、広すぎる、入れ子になっている、重複している、不正なエントリによるマウントポリシーの意図しない拡大

### 保護できないもの

- workspace と allowlist 内の全リポジトリは、エージェントの信頼境界内です。Git hook や隠しファイルも含め、エージェントはその中のファイルやスクリプトを読み取り、書き込み、削除、実行できます。
- エージェントは専用コンテナ内の rootless Docker デーモンを操作でき、その境界内で見えるパスをマウントしたコンテナを作成できます。
- 外側のコンテナランタイム、rootless Docker を実行する privileged な `docker` サービス、ホストカーネル、追加のホストマウントは、デプロイ環境の信頼上の前提として残ります。
- SSH agent の転送により、SSH agent に読み込まれた鍵を使った認証操作が可能になります。workspace 内の任意のプロセスは、中継を介して認証を要求できます。
- 本プロジェクトは、Docker Sandboxes が提供する microVM による隔離境界、認証情報プロキシ、通信を原則拒否するネットワークポリシー（deny-by-default）を提供しません。

## Docker Sandboxes との比較

Docker Sandboxes は、Docker が別途提供するエージェント向けの隔離開発環境です。
サンドボックスごとに microVM、専用の Docker Engine とファイルシステムを使い、
セキュリティモデルとしてホスト側の認証情報プロキシと deny-by-default の外向き
TCP 通信も提供します。ここでは比較対象として扱うだけで、本プロジェクトが
Docker Sandboxes に依存するわけではありません。

Docker 公式ドキュメントの [Sandboxes 概要](https://docs.docker.com/ai/sandboxes/)、[複数の workspace](https://docs.docker.com/ai/sandboxes/usage/#multiple-workspaces)、[環境ファイル](https://docs.docker.com/ai/sandboxes/configuration/environment-files/)、[セキュリティモデル](https://docs.docker.com/ai/sandboxes/security/)、[デフォルトのセキュリティ設定](https://docs.docker.com/ai/sandboxes/security/defaults/) も参照してください。

どちらも複数のリポジトリをまたいだ作業に対応できます。Docker Sandboxes では、複数のリポジトリを含む親ディレクトリを primary workspace にしたり、additional workspace を追加したりできます。また、実験的な `sbxenv.yaml` で workspace を定義することもできます。したがって、「複数リポジトリを扱えること」「1つの Sandbox を起動して使い続けられること」「設定ファイルで workspace を定義できること」は、本プロジェクトだけの特徴ではありません。

違いは、リポジトリの公開範囲をどのように管理するかにあります。本プロジェクトでは、リポジトリへのアクセスを `.devcontainer/allowlist.tsv` という、リポジトリで管理・レビューできるポリシーとして扱います。

- 追加するリポジトリを、ホスト側のパスとコンテナ側のマウント先とともに1件ずつ明示できます。
- 同じ親ディレクトリにある兄弟リポジトリでも、allowlist に登録しなければ公開されません。
- `prepare-mounts` が、起動前に存在しないパス、Git リポジトリでないパス、広すぎる親ディレクトリ、入れ子や重複するエントリ、不正なコンテナ側パスを拒否します。
- 許可したリポジトリを、`workspace` サービスと、rootless Docker デーモンを実行する専用コンテナである `docker` サービスの双方に、明示したパスでマウントします。

そのため、共有された親ディレクトリ全体を公開することなく、1つの標準的な Dev Container の中で `/workspaces/api` と `/workspaces/shared-lib` のような選択済みのリポジトリを行き来できます。Docker Sandboxes でも、親ディレクトリを primary workspace にしたり、additional workspace を設定したりすれば、同様の操作は可能です。本プロジェクトの違いは、複数リポジトリ対応そのものではなく、選択的でポリシー主導のホスト側パスとコンテナ側マウント先の対応付けを、Dev Container / Compose との統合とともに提供する点にあります。

Docker Sandboxes は、サンドボックスごとの microVM を主な信頼境界とし、専用の Docker Engine とファイルシステムを提供します。また、外部への TCP 通信を deny-by-default ポリシーでプロキシし、認証情報そのものを VM 内に渡さず、ホスト側のプロキシ経由で提供できます。自律的に動作するエージェントや信頼できないエージェントに対して、強い隔離を優先する場合には、これらの性質が適しています。

選択的なリポジトリ公開と、使い慣れた Dev Container / Compose ワークフローを優先するなら本プロジェクトが適しています。自律的に動作するエージェントや信頼できないエージェントに対して、VM・ネットワーク・認証情報をより強く隔離するデフォルト設定を優先するなら Docker Sandboxes が適しています。

## 日常の使い方

workspace 内では、次のようにリポジトリで定めた通常のコマンドを使います。

```sh
mise install
mise run test
docker compose up
```

Codex と Claude は通常のコマンドで起動できます。プロジェクト固有のエージェント設定は、ユーザーが管理するものとしています。本リポジトリは `.codex/config.toml` や `.claude/settings.json` を規定しません。

Docker や Compose を使うときは、設定されたコンテナ内パスから実行してください。`DOCKER_HOST=unix:///docker-socket/docker.sock` は、rootless Docker デーモンを実行する専用コンテナ内のソケットを指します。`/var/run/docker.sock` はそのデーモンのソケットへの互換用シンボリックリンクに過ぎず、ホストの socket ではありません。

SSH の利用は任意です。workspace で SSH agent が必要な場合だけ `SSH_AUTH_SOCK` を明示的に設定し、workspace 内の任意のプロセスが認証を要求できるようになることを理解した上で使ってください。SSH 鍵ファイルやホストの `.ssh` ディレクトリはマウントしないでください。

## 検証

リポジトリのルートから検証スイートを実行します。

```sh
bash tests/validate.sh
```

allowlist の生成・検証処理、ユニットテスト、Compose 設定を検査します。主に静的・ローカルな検証であり、実際の DNS 接続、外部ネットワークの挙動、デプロイ環境固有のすべてのセキュリティ特性を証明するものではありません。Dev Container 起動後にそれらが重要となる場合は、rootless Docker デーモン、内部コンテナからの実際の DNS 名前解決、BuildKit を使う代表的な build 経路を別途検証してください。

## ドキュメント

- [利用ガイド](docs/usage.ja.md)
- [セキュリティモデル](docs/security-model.ja.md)
- [allowlist ポリシー](.devcontainer/allowlist.tsv)
- [Dev Container 設定](.devcontainer/)

## ライセンス

[MIT License](LICENSE)
