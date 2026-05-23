# ひじきの消し方などに困った場合はここを読んでください

ひじき豆はエディタを間違えて消すとエディタはもう一度起動するまで出ていきません
ですが、エディタを消してしまってもexeファイルをもう一度起動すると、ひじき豆を消すことができます。
他にも、ひじき豆をどうにかひじき豆をクリックしてctrl+Hを押すことで消すこともできます。
## exe 生成時の依存関係

Discord Rich Presence を有効にするには、ビルド環境に `pypresence` と `pyinstaller` をインストールしてください。

```bash
python -m pip install -r requirements.txt
python -m PyInstaller hijikimame_desktop.spec
```

`hijikimame_desktop.spec` を使うことで、`pypresence` のサブモジュールも含めて exe を生成できます。
