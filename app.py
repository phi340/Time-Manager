from flask import Flask, render_template, request, redirect, session, jsonify, flash, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import sqlite3
import google.generativeai as genai

app = Flask(__name__)
app.secret_key = 'algk2gla8v8g33i4inMMnndkLzaqz32321EEs'

# Cấu hình Gemini API
api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=api_key)

def get_db():
	conn = sqlite3.connect('database.db')
	conn.row_factory = sqlite3.Row
	conn.execute('PRAGMA encoding = "UTF-8";')
	return conn

# KHỞI TẠO DATABASE
with get_db() as conn:
	conn.execute('''CREATE TABLE IF NOT EXISTS tasks (
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					content TEXT,
					status TEXT DEFAULT 'todo',
					start_time TEXT, 
					end_time TEXT,
					user_id INTEGER)''')

	conn.execute('''CREATE TABLE IF NOT EXISTS users (
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					username TEXT UNIQUE NOT NULL,
					password TEXT NOT NULL)''')

	conn.execute('''CREATE TABLE IF NOT EXISTS roadmaps (
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					title TEXT NOT NULL,
					user_id INTEGER)''')

	conn.execute('''CREATE TABLE IF NOT EXISTS milestones (
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					roadmap_id INTEGER,
					content TEXT,
					position INTEGER, 
					is_completed INTEGER DEFAULT 0,
					FOREIGN KEY(roadmap_id) REFERENCES roadmaps(id))''')
	
	conn.execute('''CREATE TABLE IF NOT EXISTS notes (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				user_id INTEGER,
				title TEXT,
				content TEXT,
				color TEXT DEFAULT '#FFE5D9',
				position_x INTEGER DEFAULT 0,
				position_y INTEGER DEFAULT 0,
				created_at TEXT)''')

# --- TRANG CHỦ ---
@app.route('/')
def index():
	return render_template('home.html')

# --- CÁC TRANG FOOTER ---
@app.route('/about')
def about():
	return render_template('about.html')

@app.route('/terms')
def terms():
	return render_template('terms.html')

@app.route('/privacy')
def privacy():
	return render_template('privacy.html')

# --- TRANG CALENDAR ---
@app.route('/calendar')
def calendar_page():
	if 'user_id' not in session:
		return redirect('/login')
	return render_template('calendar.html')

# --- TRANG TO-DO ---
@app.route('/todo')
def todo_page():
	if 'user_id' not in session:
		return redirect('/login')
	
	user_id = session['user_id']
	conn = get_db()
	tasks = conn.execute('SELECT * FROM tasks WHERE user_id = ?', (user_id,)).fetchall()
	conn.close()
	return render_template('todo.html', tasks=tasks)

# --- API XÓA TASK ---
@app.route('/delete_event/<int:id>')
@app.route('/delete/<int:id>')
def delete(id):
	if 'user_id' in session:
		conn = get_db()
		conn.execute('DELETE FROM tasks WHERE id = ? AND user_id = ?', (id, session['user_id']))
		conn.commit()
		conn.close()
	return jsonify({'status': 'success'})

# --- API CẬP NHẬT TRẠNG THÁI ---
@app.route('/update_status/<int:id>', methods=['POST'])
def update_status(id):
	if 'user_id' in session:
		new_status = request.form.get('status')
		conn = get_db()
		conn.execute('UPDATE tasks SET status = ? WHERE id = ? AND user_id = ?', 
					 (new_status, id, session['user_id']))
		conn.commit()
		conn.close()
	return redirect('/todo')

# --- ĐĂNG KÝ ---
@app.route('/register', methods=['GET', 'POST'])
def register():
	if request.method == 'POST':
		user = request.form.get('username')
		pwd = request.form.get('password')
		
		if not user or not pwd:
			flash('Vui lòng nhập đầy đủ tên và mật khẩu!', 'warning')
			return redirect('/register')

		hashed_pwd = generate_password_hash(pwd)
		try:
			conn = get_db()
			conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (user, hashed_pwd))
			conn.commit()
			conn.close()
			
			flash('Đăng ký thành công! Bạn có thể đăng nhập ngay bây giờ.', 'success')
			return redirect('/login') 
			
		except sqlite3.IntegrityError:
			flash('Tên này có người dùng rồi, hãy chọn tên khác nhé!', 'danger')
			return redirect('/register')
			
	return render_template('register.html')

# --- ĐĂNG NHẬP ---
@app.route('/login', methods=['GET', 'POST'])
def login():
	if request.method == 'POST':
		user_input = request.form.get('username')
		pwd_input = request.form.get('password')
		conn = get_db()
		user_data = conn.execute('SELECT * FROM users WHERE username = ?', (user_input,)).fetchone()
		conn.close()

		if user_data and check_password_hash(user_data[2], pwd_input):
			session['user_id'] = user_data[0]
			session['username'] = user_data[1]
			return redirect('/')
		
		flash('Sai thông tin đăng nhập!', 'danger')
		return redirect('/login')
	
	return render_template('login.html')

# --- ĐĂNG XUẤT ---
@app.route('/logout')
def logout():
	session.clear()
	return redirect('/')

# --- API CHO CALENDAR ---
@app.route('/get_events')
def get_events():
	if 'user_id' not in session: 
		return jsonify([])
	
	conn = get_db()
	rows = conn.execute('SELECT id, content, start_time, end_time FROM tasks WHERE user_id = ? AND start_time IS NOT NULL', 
						(session['user_id'],)).fetchall()
	conn.close()
	
	events = []
	for row in rows:
		events.append({
			'id': row[0],
			'title': row[1],
			'start': row[2],
			'end': row[3],
			'backgroundColor': '#1a73e8',
			'borderColor': '#1a73e8'
		})
	return jsonify(events)

@app.route('/add_event', methods=['POST'])
def add_event():
	if 'user_id' not in session: 
		return jsonify({'status': 'error'})
	
	data = request.get_json()
	conn = get_db()
	conn.execute('INSERT INTO tasks (content, start_time, end_time, user_id, status) VALUES (?, ?, ?, ?, ?)',
				 (data['title'], data['start'], data['end'], session['user_id'], 'doing'))
	conn.commit()
	conn.close()
	return jsonify({'status': 'success'})

@app.route('/update_event', methods=['POST'])
def update_event():
	if 'user_id' not in session: 
		return jsonify({'status': 'error'})
	
	data = request.get_json()
	conn = get_db()
	conn.execute('UPDATE tasks SET start_time = ?, end_time = ? WHERE id = ? AND user_id = ?',
				 (data['start'], data['end'], data['id'], session['user_id']))
	conn.commit()
	conn.close()
	return jsonify({'status': 'success'})

# --- API CHO TO-DO ---
@app.route('/add_todo', methods=['POST'])
def add_todo():
	if 'user_id' not in session: 
		return redirect('/login')
		
	content = request.form.get('content')
	if content:
		conn = get_db()
		conn.execute('INSERT INTO tasks (content, user_id, status) VALUES (?, ?, ?)', 
					 (content, session['user_id'], 'todo'))
		conn.commit()
		conn.close()
	return redirect('/todo')

# --- TRANG GIAO DIỆN NOTES ---
@app.route('/notes')
def notes_page():
	if 'user_id' not in session:
		return redirect('/login')
	conn = get_db()
	# Lấy thêm các trường title, position_x, position_y
	notes = conn.execute('SELECT * FROM notes WHERE user_id = ?', (session['user_id'],)).fetchall()
	conn.close()
	return render_template('notes.html', notes=notes)

# --- API THÊM NOTE (Dành cho Fetch JSON) ---
@app.route('/add_note', methods=['POST'])
def add_note():
	if 'user_id' not in session:
		return jsonify({'status': 'error'}), 401
	
	data = request.get_json() # Lấy dữ liệu JSON từ JS
	conn = get_db()
	conn.execute('''INSERT INTO notes (title, content, color, position_x, position_y, user_id) 
					VALUES (?, ?, ?, ?, ?, ?)''', 
				 (data.get('title'), data.get('content'), data.get('color'), 
				  data.get('position_x'), data.get('position_y'), session['user_id']))
	conn.commit()
	conn.close()
	return jsonify({'status': 'success'})

# --- API CẬP NHẬT NOTE (Dành cho Fetch JSON) ---
@app.route('/update_note/<int:note_id>', methods=['POST'])
def update_note(note_id):
	if 'user_id' not in session:
		return jsonify({'status': 'error'}), 401
	
	data = request.get_json()
	conn = get_db()
	conn.execute('''UPDATE notes SET title = ?, content = ?, color = ?, position_x = ?, position_y = ? 
					WHERE id = ? AND user_id = ?''',
				 (data.get('title'), data.get('content'), data.get('color'), 
				  data.get('position_x'), data.get('position_y'), note_id, session['user_id']))
	conn.commit()
	conn.close()
	return jsonify({'status': 'success'})

# --- API XÓA NOTE ---
@app.route('/delete_note/<int:note_id>')
def delete_note(note_id):
	if 'user_id' not in session:
		return jsonify({'status': 'error'}), 401
	conn = get_db()
	conn.execute('DELETE FROM notes WHERE id = ? AND user_id = ?', (note_id, session['user_id']))
	conn.commit()
	conn.close()
	return jsonify({'status': 'success'})

# --- API CHO ROADMAP ---
@app.route('/roadmaps')
def roadmaps():
	if 'user_id' not in session: 
		return redirect('/login')
	
	conn = get_db()
	roadmaps_raw = conn.execute('SELECT * FROM roadmaps WHERE user_id = ?', (session['user_id'],)).fetchall()
	
	roadmaps = []
	for r in roadmaps_raw:
		milestones = conn.execute('SELECT * FROM milestones WHERE roadmap_id = ?', (r['id'],)).fetchall()
		total = len(milestones)
		completed = len([m for m in milestones if m['is_completed'] == 1])
		is_completed = total > 0 and completed == total
		
		roadmaps.append({
			'id': r['id'],
			'title': r['title'],
			'user_id': r['user_id'],
			'is_completed': is_completed
		})
	
	conn.close()
	return render_template('roadmaps.html', roadmaps=roadmaps)

@app.route('/add_roadmap', methods=['POST'])
def add_roadmap():
	if 'user_id' not in session: 
		return redirect('/login')
	
	title = request.form.get('title')
	if title:
		conn = get_db()
		conn.execute('INSERT INTO roadmaps (title, user_id) VALUES (?, ?)', (title, session['user_id']))
		conn.commit()
		conn.close()
	return redirect('/roadmaps')

@app.route('/roadmap/<int:roadmap_id>')
def view_roadmap(roadmap_id):
	if 'user_id' not in session: 
		return redirect('/login')
	
	conn = get_db()
	# 🔒 FIX: Thêm kiểm tra user_id để bảo mật
	roadmap = conn.execute('SELECT * FROM roadmaps WHERE id = ? AND user_id = ?', 
						   (roadmap_id, session['user_id'])).fetchone()
	
	if roadmap is None:
		conn.close()
		flash('Không tìm thấy lộ trình hoặc bạn không có quyền truy cập!', 'danger')
		return redirect('/roadmaps')

	milestones = conn.execute('SELECT * FROM milestones WHERE roadmap_id = ? ORDER BY position', 
							  (roadmap_id,)).fetchall()
	
	total = len(milestones)
	completed = len([m for m in milestones if m['is_completed'] == 1])
	progress = int((completed / total) * 100) if total > 0 else 0
	
	conn.close()
	return render_template('roadmap.html', roadmap=roadmap, milestones=milestones, progress=progress)

@app.route('/add_milestone/<int:roadmap_id>', methods=['POST'])
def add_milestone(roadmap_id):
	if 'user_id' not in session: 
		return redirect('/login')
	
	content = request.form.get('content')
	if not content:
		return redirect(f'/roadmap/{roadmap_id}')
	
	conn = get_db()
	
	# 🔒 Kiểm tra roadmap có thuộc user không
	roadmap = conn.execute('SELECT id FROM roadmaps WHERE id = ? AND user_id = ?', 
						   (roadmap_id, session['user_id'])).fetchone()
	
	if not roadmap:
		conn.close()
		flash('Không có quyền thêm milestone vào roadmap này!', 'danger')
		return redirect('/roadmaps')
	
	row = conn.execute('SELECT COUNT(*) as total FROM milestones WHERE roadmap_id = ?', 
					   (roadmap_id,)).fetchone()
	new_position = row['total'] + 1
	
	conn.execute('INSERT INTO milestones (roadmap_id, content, position) VALUES (?, ?, ?)', 
				 (roadmap_id, content, new_position))
	conn.commit()
	conn.close()
	
	return redirect(f'/roadmap/{roadmap_id}')

@app.route('/toggle_milestone/<int:m_id>/<int:r_id>')
def toggle_milestone(m_id, r_id):
	if 'user_id' not in session: 
		return redirect('/login')
	
	conn = get_db()
	conn.execute('UPDATE milestones SET is_completed = 1 - is_completed WHERE id = ?', (m_id,))
	conn.commit()
	conn.close()
	return redirect(f'/roadmap/{r_id}')

@app.route('/delete_milestone/<int:m_id>/<int:r_id>')
def delete_milestone(m_id, r_id):
	if 'user_id' not in session: 
		return redirect('/login')
	
	conn = get_db()
	conn.execute('DELETE FROM milestones WHERE id = ?', (m_id,))
	conn.commit()
	conn.close()
	return redirect(f'/roadmap/{r_id}')

@app.route('/delete_roadmap/<int:roadmap_id>')
def delete_roadmap(roadmap_id):
	if 'user_id' not in session: 
		return redirect('/login')
	
	conn = get_db()
	# Kiểm tra roadmap có thuộc user không
	roadmap = conn.execute('SELECT id FROM roadmaps WHERE id = ? AND user_id = ?', 
						   (roadmap_id, session['user_id'])).fetchone()
	
	if roadmap:
		# Xóa tất cả milestones của roadmap này trước
		conn.execute('DELETE FROM milestones WHERE roadmap_id = ?', (roadmap_id,))
		# Sau đó xóa roadmap
		conn.execute('DELETE FROM roadmaps WHERE id = ?', (roadmap_id,))
		conn.commit()
		flash('Đã xóa lộ trình thành công!', 'success')
	else:
		flash('Không có quyền xóa lộ trình này!', 'danger')
	
	conn.close()
	return redirect('/roadmaps')

@app.route('/static/<path:filename>')
def serve_static(filename):
	return send_from_directory('static', filename)

@app.route('/chat')
def chat_page():
	if 'user_id' not in session:
		return redirect('/login')
	return render_template('chat.html')

@app.route('/api/chat', methods=['POST'])
def chat_api():
	if 'user_id' not in session:
		return jsonify({'error': 'Unauthorized'}), 401
	
	data = request.get_json()
	user_message = data.get('message', '')
	
	if not user_message:
		return jsonify({'error': 'Empty message'}), 400
	
	try:
		user_id = session['user_id']
		username = session['username']
		
		# Lấy context từ database
		conn = get_db()
		
		# Tasks hôm nay
		today_tasks = conn.execute(
			'SELECT content, status FROM tasks WHERE user_id = ? AND date(start_time) = date("now")',
			(user_id,)
		).fetchall()
		
		# Tasks sắp tới
		upcoming = conn.execute(
			'SELECT content, start_time FROM tasks WHERE user_id = ? AND start_time > datetime("now") ORDER BY start_time LIMIT 3',
			(user_id,)
		).fetchall()
		
		conn.close()
		
		# Tạo context cho AI
		context = f"""Bạn là trợ lý cá nhân thông minh và thân thiện của {username}.
Bạn giúp họ quản lý thời gian, công việc và luôn sẵn sàng lắng nghe.

Tính cách của bạn:
- Nhiệt tình, lạc quan, luôn động viên
- Thân thiện như người bạn thân
- Nói chuyện tự nhiên, không quá formal
- Quan tâm đến cảm xúc và tâm trạng của user
- Nhắc nhở nhẹ nhàng, khéo léo
- Có thể hài hước nhẹ nhàng khi phù hợp
- Thỉnh thoảng dùng emoji 😊✨💪 khi cần nhấn mạnh"""
		
		if today_tasks:
			context += f"\nCông việc hôm nay:\n"
			for task in today_tasks:
				status_vn = {'todo': 'Chưa làm', 'doing': 'Đang làm', 'done': 'Đã xong'}
				context += f"- {task['content']} ({status_vn[task['status']]})\n"
		
		if upcoming:
			context += f"\nSắp tới:\n"
			for task in upcoming:
				context += f"- {task['content']} lúc {task['start_time']}\n"
		
		context += f"\nUser nói: {user_message}\n\nHãy trả lời một cách tự nhiên, thân thiện. Nếu user hỏi về công việc, hãy dựa vào thông tin trên."
		
		# Gọi Gemini API
		model = genai.GenerativeModel('gemini-2.5-flash')
		response = model.generate_content(context)
		
		return jsonify({
			'reply': response.text,
			'timestamp': datetime.now().isoformat()
		})
		
	except Exception as e:
		print(f"Error in chat: {e}")
		return jsonify({'error': 'Lỗi kết nối AI'}), 500

# ⚠️ QUAN TRỌNG: Dòng này PHẢI ở cuối cùng!
if __name__ == '__main__':
	app.run(debug=True)