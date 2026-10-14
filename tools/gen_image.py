#!/usr/bin/env python3
"""ChatGPT(OpenAI) / Gemini でスタンプの元画像(コマ割りシート)を生成する。

環境変数:
  OPENAI_API_KEY  … ChatGPT(画像生成)を使う場合
  GEMINI_API_KEY  … Gemini(画像生成)を使う場合
  OPENAI_IMAGE_MODEL / GEMINI_IMAGE_MODEL … モデル名を変えたいとき

クラウド環境で Gemini のキーを「ネットワークシークレット(Bearer, 許可ウェブサイト
generativelanguage.googleapis.com, パス /v1beta/openai/)」に登録した場合は、キーが
セッションから見えないため --provider gemini-secret を使う(通信時に自動でキーが付く)。
  GEMINI_COMPAT_IMAGE_MODEL … この方式で使う画像モデル(既定 imagen-4.0-generate-001)

例:
  python3 tools/gen_image.py --provider auto -o work/neko/design/01_gen.png \\
      --prompt "$(cat work/neko/design/01_prompt.txt)"
"""
import argparse
import base64
import json
import os
import sys
import urllib.request
from pathlib import Path


def post(url, payload, headers):
    req = urllib.request.Request(url, json.dumps(payload).encode(), {"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"APIエラー {e.code}: {e.read().decode(errors='replace')[:500]}")


def openai(prompt):
    model = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1")
    res = post("https://api.openai.com/v1/images/generations",
               {"model": model, "prompt": prompt, "size": "1536x1024", "n": 1},
               {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"})
    return base64.b64decode(res["data"][0]["b64_json"])


def gemini(prompt):
    model = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    res = post(url, {"contents": [{"parts": [{"text": prompt}]}]},
               {"x-goog-api-key": os.environ["GEMINI_API_KEY"]})
    for part in res["candidates"][0]["content"]["parts"]:
        if "inlineData" in part:
            return base64.b64decode(part["inlineData"]["data"])
    sys.exit("Geminiから画像が返りませんでした: " + json.dumps(res)[:500])


def gemini_secret(prompt):
    """Gemini の OpenAI 互換窓口。Authorization ヘッダーはプロキシが付ける。"""
    model = os.environ.get("GEMINI_COMPAT_IMAGE_MODEL", "imagen-4.0-generate-001")
    res = post("https://generativelanguage.googleapis.com/v1beta/openai/images/generations",
               {"model": model, "prompt": prompt, "n": 1, "response_format": "b64_json"}, {})
    return base64.b64decode(res["data"][0]["b64_json"])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--provider", choices=["auto", "openai", "gemini", "gemini-secret"], default="auto")
    p.add_argument("--prompt", required=True)
    p.add_argument("-o", "--out", required=True)
    a = p.parse_args()

    provider = a.provider
    if provider == "auto":
        provider = "openai" if os.environ.get("OPENAI_API_KEY") else "gemini" if os.environ.get("GEMINI_API_KEY") else None
    if provider is None:
        print("APIキーの環境変数がないため、ネットワークシークレット方式(gemini-secret)で試します")
        provider = "gemini-secret"

    data = {"openai": openai, "gemini": gemini, "gemini-secret": gemini_secret}[provider](a.prompt)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    print(f"{provider} で生成: {out}")


if __name__ == "__main__":
    main()
