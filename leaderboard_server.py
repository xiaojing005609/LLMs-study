import os
import json
import sqlite3
import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

# 数据库文件路径
DB_FILE = 'leaderboard.db'

# 获取数据库连接
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # 允许通过列名访问
    return conn

# 初始化数据库
def init_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    # 创建排行榜表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leaderboard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            score INTEGER NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    print(f"数据库初始化完成: {DB_FILE}")

# 加载排行榜数据
def load_leaderboard():
    conn = get_db_connection()
    cursor = conn.cursor()
    # 获取前10名，按分数降序排序
    cursor.execute('SELECT name, score FROM leaderboard ORDER BY score DESC LIMIT 10')
    scores = []
    for row in cursor.fetchall():
        scores.append({
            'name': row['name'],
            'score': row['score']
        })
    conn.close()
    print(f"从数据库获取排行榜数据，返回 {len(scores)} 条记录")
    return scores

# 保存新分数
def save_score(name, score):
    conn = get_db_connection()
    cursor = conn.cursor()
    timestamp = datetime.datetime.now().isoformat()
    cursor.execute('INSERT INTO leaderboard (name, score, timestamp) VALUES (?, ?, ?)', (name, score, timestamp))
    conn.commit()
    conn.close()

class LeaderboardHandler(BaseHTTPRequestHandler):
    # 自定义请求日志
    def log_request(self, code='-', size='-'):
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f'[{now}] {self.client_address[0]} - {self.command} {self.path} - HTTP/{self.request_version} - {code}')

    # 设置CORS头
    def _set_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    # 处理OPTIONS请求
    def do_OPTIONS(self):
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    # 处理排行榜获取请求
    def _handle_get_scores(self):
        scores = load_leaderboard()
        
        self.send_response(200)
        self._set_cors_headers()
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        # 将字典转换为JSON字符串
        response = json.dumps(scores)
        self.wfile.write(response.encode('utf-8'))
        print(f"已发送排行榜数据，共{len(scores)}条记录")

    # 处理分数提交请求
    def _handle_submit_score(self):
        # 仅处理POST请求
        if self.command != 'POST':
            self.send_response(405)
            self.end_headers()
            return
        
        # 读取请求体
        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            print(f"接收提交请求: {body}")
            data = json.loads(body)
            
            # 获取并清理数据
            name = str(data.get('name', '')).strip()
            score = data.get('score', 0)
            
            # 转换分数为整数（如果可能）
            if not isinstance(score, int):
                try:
                    score = int(float(score))
                except (ValueError, TypeError):
                    score = 0
            
            # 更宽松的验证逻辑
            if not name:
                name = "匿名玩家"
            if score < 0:
                score = 0
            
            # 限制名称长度
            if len(name) > 50:
                name = name[:50]
            
            # 保存分数
            save_score(name, score)
            
            # 返回成功响应
            self.send_response(201)
            self._set_cors_headers()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            success_response = json.dumps({'message': '分数已保存'})
            self.wfile.write(success_response.encode('utf-8'))
            print(f"保存新分数: {name} - {score}")
        except json.JSONDecodeError:
            print(f"JSON解析错误: {body}")
            self.send_response(400)
            self._set_cors_headers()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            error_response = json.dumps({'error': '无效的JSON格式'})
            self.wfile.write(error_response.encode('utf-8'))
        except Exception as e:
            print(f"处理分数提交时出错: {str(e)}")
            self.send_response(500)
            self._set_cors_headers()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            error_response = json.dumps({'error': '服务器内部错误'})
            self.wfile.write(error_response.encode('utf-8'))

    # 提供静态文件服务
    def _serve_static_file(self):
        path = self.path
        # 移除查询参数
        if '?' in path:
            path = path.split('?')[0]
        
        # 如果路径是根目录，返回snake_game.html
        if path == '/':
            path = '/snake_game.html'
        
        # 安全检查：防止目录遍历攻击
        if '..' in path or '\\' in path:
            print(f"安全警告: 尝试访问非法路径 {path}")
            self.send_response(403)
            self.end_headers()
            return
        
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
            return
        
        # 读取并发送文件
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            
            self.send_response(200)
            self._set_cors_headers()  # 添加CORS头
            self.send_header('Content-Type', mime_type)
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
            print(f"提供静态文件: {path}")
        except Exception as e:
            print(f"读取文件错误 {file_path}: {str(e)}")
            self.send_response(500)
            self.end_headers()

    # 处理GET请求
    def do_GET(self):
        if self.path == '/api/scores':
            self._handle_get_scores()
        else:
            self._serve_static_file()

    # 处理POST请求
    def do_POST(self):
        if self.path == '/api/submit':
            self._handle_submit_score()
        else:
            self.send_response(404)
            self.end_headers()

# 主函数
def run(server_class=HTTPServer, handler_class=LeaderboardHandler, port=8080):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f"排行榜服务器启动在端口 {port}")
    print(f"游戏访问地址: http://localhost:{port}/snake_game.html")
    print(f"API端点:")
    print(f"  GET  http://localhost:{port}/api/scores - 获取排行榜数据")
    print(f"  POST http://localhost:{port}/api/submit - 提交新分数")
    print("数据库已初始化，排行榜数据将存储在 leaderboard.db 文件中")
    print("按 Ctrl+C 停止服务器")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    print("服务器已停止")

if __name__ == '__main__':
    # 初始化数据库
    init_database()
    # 启动服务器
    run()