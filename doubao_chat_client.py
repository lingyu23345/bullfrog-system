#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
豆包（火山方舟大模型）公网对话调用客户端
========================================
- 直接通过 HTTPS 对接火山引擎方舟 API，无需本地代理 / 局域网 / 内网环境。
- 依赖：仅 Python 标准库（urllib / json），安装好 Python 即可直接运行。
- 错误处理：覆盖网络异常、鉴权失败(401/403)、限流(429)、服务端错误(5xx)、响应解析失败。

用法：
    # 方式一：交互式对话
    python doubao_chat_client.py

    # 方式二：单次提问（非交互）
    python doubao_chat_client.py -m "用一句话解释什么是 OCR"

    # 覆盖默认模型
    python doubao_chat_client.py --model doubao-seed-1.6-250615 -m "你好"

    # 通过环境变量传入密钥（推荐，避免密钥写进代码）
    export ARK_API_KEY="ark-xxxx"
    export ARK_MODEL="doubao-seed-1.6-250615"
    python doubao_chat_client.py
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.error

# ====================== 配置区 ======================
# API Key：优先读环境变量 ARK_API_KEY；否则使用下面的占位值（请替换）。
# ⚠️ 安全提示：不要把真实密钥提交到公开仓库。推荐用环境变量方式传入。
API_KEY = os.environ.get("ARK_API_KEY", "在此填写你的ARK_API_KEY")

# 火山方舟 API 接入点（公网 HTTPS，无需本地代理）
ENDPOINT = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"

# 模型 ID：在方舟控制台「模型」中获取，例如 doubao-seed-2-0-lite-260428
# 也可用环境变量 ARK_MODEL 覆盖
MODEL = os.environ.get("ARK_MODEL", "doubao-seed-2-0-lite-260428")

# 请求超时时间（秒）
TIMEOUT = 60

# 系统提示词（可选）
SYSTEM_PROMPT = "你是一个有帮助的中文助手，回答简洁准确。"
# ====================================================


class DoubaoClient:
    """豆包对话客户端：封装 HTTPS 请求与错误处理。"""

    def __init__(self, api_key=None, endpoint=None, model=None, timeout=None):
        self.api_key = api_key or API_KEY
        self.endpoint = endpoint or ENDPOINT
        self.model = model or MODEL
        self.timeout = timeout or TIMEOUT

        if not self.api_key or self.api_key.startswith("在此填写"):
            raise ValueError(
                "未配置 API Key：请设置环境变量 ARK_API_KEY，"
                "或在文件顶部配置区填写真实密钥。"
            )

    def chat(self, user_message, history=None, temperature=0.7):
        """
        发送一条用户消息，返回豆包回复文本。

        :param user_message: 用户输入内容
        :param history: 可选对话历史，格式 [(role, content), ...]，用于多轮上下文
        :param temperature: 生成随机性 0~1
        :return: 豆包回复文本
        """
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if history:
            messages.extend({"role": r, "content": c} for r, c in history)
        messages.append({"role": "user", "content": user_message})

        payload = json.dumps({
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }).encode("utf-8")

        req = urllib.request.Request(
            self.endpoint, data=payload, method="POST"
        )
        req.add_header("Authorization", f"Bearer {self.api_key}")
        req.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            self._handle_http_error(e)
        except urllib.error.URLError as e:
            # 网络层异常（DNS 失败 / 无法连接 / 超时）
            reason = getattr(e, "reason", str(e))
            raise ConnectionError(
                f"网络异常，无法连接豆包服务（{self.endpoint}）：{reason}"
            ) from e
        except TimeoutError:
            raise ConnectionError(
                f"请求超时（>{self.timeout}s），豆包服务未在规定时间内响应。"
            )
        except Exception as e:
            raise RuntimeError(f"未知错误：{e}") from e

        # 解析响应
        try:
            data = json.loads(body)
            return data["choices"][0]["message"]["content"].strip()
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as e:
            raise ValueError(f"响应解析失败：{e}；原始内容前200字符：{body[:200]}")

    @staticmethod
    def _handle_http_error(e):
        """把 HTTP 错误码转换为清晰、可操作的异常。"""
        code = e.code
        try:
            detail = json.loads(e.read().decode("utf-8"))
            msg = (
                detail.get("error", {}).get("message")
                or detail.get("message")
                or str(e.reason)
            )
        except Exception:
            msg = str(e.reason)

        if code in (401, 403):
            raise PermissionError(
                f"鉴权失败（HTTP {code}）：{msg}。"
                f"请确认 API Key 有效、未过期，且已对该模型授权。"
            )
        if code == 404:
            raise ValueError(
                f"模型或接口不存在（HTTP 404）：{msg}。"
                f"请检查接入点 ENDPOINT 与模型 ID MODEL 是否正确。"
            )
        if code == 429:
            raise RuntimeError(f"触发限流（HTTP 429）：{msg}。请稍后重试。")
        if 500 <= code < 600:
            raise RuntimeError(f"豆包服务端错误（HTTP {code}）：{msg}。请稍后重试。")
        raise RuntimeError(f"请求被拒绝（HTTP {code}）：{msg}")


def interactive():
    """交互式对话模式。"""
    try:
        client = DoubaoClient()
    except ValueError as e:
        print(f"[配置错误] {e}")
        sys.exit(1)

    print(f"豆包对话客户端已启动（模型：{client.model}）。输入 exit / quit 退出。")
    history = []
    while True:
        try:
            user_input = input("\n你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见。")
            break
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            print("再见。")
            break
        try:
            reply = client.chat(user_input, history=history)
            print(f"豆包> {reply}")
            history.append(("user", user_input))
            history.append(("assistant", reply))
        except (PermissionError, ConnectionError, ValueError, RuntimeError) as e:
            print(f"[调用失败] {e}")


def main():
    parser = argparse.ArgumentParser(description="豆包（火山方舟）公网对话客户端")
    parser.add_argument("-m", "--message", help="单次提问内容（不进入交互模式）")
    parser.add_argument("--model", help="覆盖默认模型 ID")
    args = parser.parse_args()

    try:
        client = DoubaoClient(model=args.model or MODEL)
    except ValueError as e:
        print(f"[配置错误] {e}")
        sys.exit(1)

    if args.message:
        try:
            reply = client.chat(args.message)
            print(reply)
        except (PermissionError, ConnectionError, ValueError, RuntimeError) as e:
            print(f"[调用失败] {e}")
            sys.exit(1)
    else:
        interactive()


if __name__ == "__main__":
    main()
