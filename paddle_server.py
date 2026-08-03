# -*- coding: utf-8 -*-
"""
豆包视觉 API 代理服务
为牛蛙收购单 OCR 识别页面提供后端代理，转发请求到火山引擎方舟 API
"""
import sys
import time
import json
import traceback
import urllib.request
import urllib.error

from flask import Flask, request, jsonify

app = Flask(__name__)


@app.after_request
def after_request(resp):
    """允许跨域，替代 flask_cors"""
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
    return resp


@app.route('/')
def index():
    """健康检查"""
    return jsonify({
        "status": "running",
        "service": "Doubao Vision API Proxy",
        "endpoints": {
            "/api/doubao": "POST - 豆包视觉API代理",
            "/health": "GET - 健康检查"
        }
    })


@app.route('/health')
def health():
    """健康检查"""
    return jsonify({"status": "ok"})


@app.route('/api/doubao', methods=['POST', 'OPTIONS'])
def doubao_proxy():
    """
    豆包视觉 API 代理
    转发请求到火山引擎方舟 Responses API，避免前端 CORS 问题
    """
    if request.method == 'OPTIONS':
        return jsonify({"ok": True})

    try:
        body = request.get_json()
        if not body:
            return jsonify({"error": "请求体不能为空"}), 400

        # 从请求 body 中取出鉴权信息，然后删除，不再转发给客户端
        api_key = body.pop('api_key', '') or request.headers.get('X-API-Key', '')
        target_url = body.pop('api_url', '') or 'https://ark.cn-beijing.volces.com/api/v3/responses'

        if not api_key:
            return jsonify({"error": "缺少 API Key"}), 400

        # 设置超时
        timeout = body.pop('_timeout', 180)

        # 构建转发请求
        req_data = json.dumps(body).encode('utf-8')
        req = urllib.request.Request(
            target_url,
            data=req_data,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            },
            method='POST'
        )

        start_time = time.time()

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_body = resp.read().decode('utf-8')
                resp_data = json.loads(resp_body) if resp_body else {}
                elapsed = round(time.time() - start_time, 2)
                resp_data['_proxy_time'] = elapsed
                return jsonify(resp_data)
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8', errors='replace')
            try:
                error_data = json.loads(error_body)
            except Exception:
                error_data = {"error": error_body}
            error_data['_proxy_status'] = e.code
            return jsonify(error_data), e.code
        except urllib.error.URLError as e:
            return jsonify({"error": f"连接豆包API失败: {str(e.reason)}"}), 502
        except Exception as e:
            return jsonify({"error": f"请求异常: {str(e)}"}), 500

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"代理服务异常: {str(e)}"}), 500


if __name__ == '__main__':
    print("=" * 50)
    print("豆包视觉 API 代理服务")
    print("=" * 50)
    print(f"Python: {sys.version.split()[0]}")
    print(f"监听地址: http://0.0.0.0:5000")
    print(f"API 端点:")
    print(f"  POST /api/doubao - 豆包视觉API代理")
    print(f"  GET  /health     - 健康检查")
    print("=" * 50)

    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
