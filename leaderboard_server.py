import json
import os
import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

# 存储排行榜数据的文件
LEADERBOARD_FILE = 'leaderboard.json'

# 确保排行榜文件存在
def ensure_leaderboard_file():
    if not os.path.exists(LEADERBOARD_FILE):
        with open(LEADERBOARD_FILE, 'w') as f:
            json.dump([], f)
        print(f"创建新的排行榜文件: {LEADERBOARD_FILE}")

# 加载排行榜数据
def load_leaderboard():
    ensure_leaderboard_file()
    try:
        with open(LEADERBOARD_FILE, 'r') as f:
            data = json.load(f)
            # 按分数降序排序
            return sorted(data, key=lambda x: x['score'], reverse=True)
    except json.JSONDecodeError:
        print("排行榜文件格式错误，返回空列表")
        return []

# 保存新分数到排行榜
def save_score(name, score):
    # 加载现有数据
    data = load_leaderboard()
    
    # 创建新记录
    new_entry = {
        'name': name.strip(),
        'score': score,
        'timestamp': datetime.datetime.now().isoformat()
    }
    
    # 添加新记录
    data.append(new_entry)
    
    # 按分数降序排序
    data.sort(key=lambda x: x['score'], reverse=True)
    
    # 只保留前100名
    data = data[:100]
    
    # 保存到文件
    with open(LEADERBOARD_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"保存新分数: {name} - {score}")
    return new_entry

class LeaderboardHandler(BaseHTTPRequestHandler):
    # 自定义请求日志
    def log_request(self, code='-', size='-'):
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f'[{now}] {self.client_address[0]} - {self.command} {self.path} - HTTP/{self.request_version} - {code}')
    
    # 处理CORS
    def _set_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
    
    # 处理OPTIONS请求
    def do_OPTIONS(self):
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()
    
    # 提供静态文件服务
    def _serve_static_file(self, path):
        # 如果路径是根目录，返回snake_game.html
        if path == '/':
            path = '/snake_game.html'
        
        # 安全检查：防止目录遍历攻击
        if '..' in path or '\\' in path:
            print(f"安全警告: 尝试访问非法路径 {path}")
            self.send_response(403)
            self.end_headers()
            return False
        
        # 映射文件扩展名到MIME类型
        mime_types = {
            '.html': 'text/html',
            '.css': 'text/css',
            '.js': 'text/javascript',
            '.json': 'application/json',
            '.txt': 'text/plain'
        }
        
        # 获取文件扩展名
        file_ext = os.path.splitext(path)[1].lower()
        mime_type = mime_types.get(file_ext, 'application/octet-stream')
        
        # 构建文件路径
        file_path = '.' + path
        
        # 检查文件是否存在
        if not os.path.isfile(file_path):
            print(f"文件不存在: {file_path}")
            self.send_response(404)
            self.end_headers()
            return False
        
        # 读取并发送文件
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            
            self.send_response(200)
            self.send_header('Content-Type', mime_type)
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
            print(f"提供静态文件: {path}")
            return True
        except Exception as e:
            print(f"读取文件错误 {file_path}: {str(e)}")
            self.send_response(500)
            self.end_headers()
            return False
    
    # 处理GET请求
    def do_GET(self):
        if self.path == '/api/scores':
            # 获取排行榜数据
            scores = load_leaderboard()
            print(f"获取排行榜数据，返回 {len(scores)} 条记录")
            
            self.send_response(200)
            self._set_cors_headers()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(scores).encode())
        else:
            # 尝试提供静态文件
            self._serve_static_file(self.path)
    
    # 处理POST请求
    def do_POST(self):
        if self.path == '/api/submit':
            # 获取请求体大小
            content_length = int(self.headers['Content-Length'])
            # 读取请求体
            post_data = self.rfile.read(content_length).decode()
            
            print(f"接收提交请求: {post_data}")
            
            # 解析表单数据
            data = {}
            for pair in post_data.split('&'):
                if '=' in pair:
                    key, value = pair.split('=')
                    data[key] = urllib.parse.unquote(value)
            
            # 验证数据
            if 'name' not in data or 'score' not in data:
                print("提交数据不完整")
                self.send_response(400)
                self._set_cors_headers()
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'Invalid name or score'}).encode())
                return
            
            try:
                # 添加新分数
                new_score = save_score(data['name'], int(data['score']))
                
                # 返回成功响应
                self.send_response(201)
                self._set_cors_headers()
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(new_score).encode())
            except Exception as e:
                print(f"保存分数错误: {str(e)}")
                self.send_response(500)
                self._set_cors_headers()
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == '__main__':
    port = 8080
    server_address = ('', port)
    httpd = HTTPServer(server_address, LeaderboardHandler)
    print(f"排行榜服务器启动在端口 {port}")
    print(f"游戏访问地址: http://localhost:{port}/snake_game.html")
    print(f"API端点:")
    print(f"  GET  http://localhost:{port}/api/scores - 获取排行榜数据")
    print(f"  POST http://localhost:{port}/api/submit - 提交新分数")
    print("按 Ctrl+C 停止服务器")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器停止")
        httpd.server_close()