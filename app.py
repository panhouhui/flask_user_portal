from flask import Flask, render_template, request, redirect, session, url_for, jsonify
import sqlite3
import os
import cv2
import time  # 新增导入
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'secret_key'

DB_NAME = 'users.db'

UPLOAD_FOLDER = 'static/uploads'
FRAME_FOLDER = 'static/frames'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(FRAME_FOLDER, exist_ok=True)


def init_db():
    if not os.path.exists(DB_NAME):
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password TEXT NOT NULL
                )
            """)


@app.route('/')
def index():
    if 'username' in session:
        return redirect('/dashboard')
    return redirect('/login')


@app.route('/login', methods=['GET', 'POST'])
def login():
    msg = ''
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
            user = c.fetchone()
            if user:
                session['username'] = username
                return redirect('/dashboard')
            else:
                msg = '用户名或密码错误'
    return render_template('login.html', msg=msg)


@app.route('/register', methods=['GET', 'POST'])
def register():
    msg = ''
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            try:
                c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
                conn.commit()
                return redirect('/login')
            except sqlite3.IntegrityError:
                msg = '用户名已存在'
    return render_template('register.html', msg=msg)


@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect('/login')
    return render_template('dashboard.html', username=session['username'])


@app.route('/content/<section>')
def content(section):
    if section == 'profile':
        # 模拟生成基准标签耗时15秒
        time.sleep(15)
        content = f"<h2>{session['last_uploaded_filename']}，基准标签生成成功</h2>"
        return jsonify(content=content)

    sections = {
        'home': '<h2>欢迎回来！</h2><p>这是首页内容。</p>',
        'profile': f'<h2>个人中心</h2><p>你好，{session.get("username", "用户")}！</p>',
        'settings': '<h2>设置</h2><p>这里是设置界面。</p>',
        'video': '''
<h2>选择处理的视频</h2>
<form id="videoForm" enctype="multipart/form-data">
    <input type="file" name="video" accept="video/*" required><br><br>
    <button type="submit">开始解析视频帧</button>
</form>
<p id="videoResult" style="margin-top: 20px; color: green;"></p>
<script>
document.getElementById('videoForm').onsubmit = function(e) {
    e.preventDefault();
    const formData = new FormData(this);
    fetch('/upload_video', {
        method: 'POST',
        body: formData
    })
    .then(res => res.json())
    .then(data => {
        if (data.message) {
            document.getElementById('videoResult').innerText = data.message;
        } else {
            document.getElementById('videoResult').innerText = "处理失败: " + data.error;
        }
    })
    .catch(err => {
        document.getElementById('videoResult').innerText = "请求出错";
    });
}
</script>
'''
    }
    return jsonify(content=sections.get(section, '未找到内容'))


@app.route('/upload_video', methods=['POST'])
def upload_video():
    if 'username' not in session:
        return jsonify({'error': '请先登录'}), 401

    video = request.files.get('video')
    if not video:
        return jsonify({'error': '没有上传视频'}), 400

    filename = secure_filename(video.filename)
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    video.save(save_path)

    # 把文件名存session，供后续访问
    session['last_uploaded_filename'] = filename

    # 提取帧
    frame_output = os.path.join(FRAME_FOLDER, os.path.splitext(filename)[0])
    saved_count, total = save_frames_from_video(save_path, frame_output)

    return jsonify({
        'message': f'帧提取完成：{saved_count}/{total}帧已保存，路径：{frame_output}'
    })


def save_frames_from_video(vid_path: str, output_dir: str):
    cap = cv2.VideoCapture(vid_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), 100]

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    saved_count = 0

    while cap.isOpened():
        current_frame_index = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
        success, frame = cap.read()
        if success:
            filename = os.path.join(output_dir, "{:05d}.jpg".format(current_frame_index))
            ret = cv2.imwrite(filename, frame, encode_params)
            if ret:
                saved_count += 1
        else:
            break

    cap.release()

    return saved_count, total_frames



@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect('/login')


if __name__ == '__main__':
    init_db()
    app.run(debug=True)