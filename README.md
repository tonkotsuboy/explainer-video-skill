# explainer-video-skill

調べた内容を、ナレーション付きの解説動画（1920x1080 の MP4）にする Claude Code のスキルです。

## できること

- 最初に「長さ・対象者・音声」を選び、参考にするコードや資料を渡すと、事実を集めて台本（`script.json`）を書きます。
- 台本の文ごとに AivisSpeech で音声を合成し、字幕・図・コード抜粋・画面キャプチャの出るタイミングを音声に合わせて揃えます。
- 読み間違えやすい語は、合成の前に質問して読み方を確定します。直した読みは自分用の読み辞書（`~/.config/explainer-video/readings.json`）に足せて、次の動画から自動で使われます。
- 書いた台本は、別のサブエージェントに読ませて、耳で聞いて分かりにくい文を直します。

## 必要なもの

- Node.js 22 以上
- [uv](https://docs.astral.sh/uv/)
- ffmpeg
- [AivisSpeech Engine](https://aivis-project.com/)（起動して `http://127.0.0.1:10101` で応答する状態にしておく）

## インストール

シンボリックリンクで入れると、`git pull` だけで更新できます。

```bash
git clone https://github.com/tonkotsuboy/explainer-video-skill
cd explainer-video-skill
mkdir -p ~/.claude/skills
ln -s "$PWD/skills/explainer-video" ~/.claude/skills/explainer-video
```

コピーで入れる場合は `cp -R skills/explainer-video ~/.claude/skills/` です（更新のたびにコピーし直します）。

自分で足した読み辞書は `~/.config/explainer-video/readings.json` にあり、スキルの外なので、どちらの方法で更新しても消えません。

## 使い方の例

Claude Code で次のように頼みます。

```
このリポジトリの認証の仕組みを、エンジニア向けの5分の解説動画にして
```

## 補足

- 動画の書き出しには [HyperFrames](https://github.com/heygen-com/hyperframes)（Apache-2.0）と [GSAP](https://gsap.com/) を使います。GSAP は無料の "Standard No Charge" ライセンスで配布されていて、OSI 承認のオープンソースライセンスではありません。
- HyperFrames は既定で匿名の利用状況を送信しますが、このスキルはすべての `hyperframes` コマンドに `HYPERFRAMES_NO_TELEMETRY=1` を付けて送信を止めます。
- 見た目（色・フォント・角丸など）は `skills/explainer-video/assets/theme.css` の1ファイルに集めてあります。1本の動画だけ変えたいときは、作業フォルダに theme.css をコピーして直すと、そちらが使われます。

## ライセンス

MIT
