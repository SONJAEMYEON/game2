import streamlit as st
import google.generativeai as genai
from PyPDF2 import PdfReader
import sqlite3
import hashlib
import uuid
from datetime import datetime
import json
import stripe

# stripe 설정 (테스트 키 사용)
stripe.api_key = "AIzaSyCzc5_C4C5MZTvITgJjqpdJNkuWNitlI18"

# 데이터베이스 초기화
def init_db():
    conn = sqlite3.connect('shop.db')
    c = conn.cursor()
    
    # 사용자 테이블
    c.execute('''
        CREATE TABLE IF NOT EXISTS users
        (id INTEGER PRIMARY KEY,
         username TEXT UNIQUE,
         password TEXT,
         api_key TEXT,
         created_at TIMESTAMP)
    ''')
    
    # 상품 테이블
    c.execute('''
        CREATE TABLE IF NOT EXISTS products
        (id INTEGER PRIMARY KEY,
         name TEXT,
         price REAL,
         description TEXT,
         image_url TEXT)
    ''')
    
    # 장바구니 테이블
    c.execute('''
        CREATE TABLE IF NOT EXISTS cart
        (id INTEGER PRIMARY KEY,
         user_id INTEGER,
         product_id INTEGER,
         quantity INTEGER,
         FOREIGN KEY (user_id) REFERENCES users (id),
         FOREIGN KEY (product_id) REFERENCES products (id))
    ''')
    
    # PDF 분석 결과 테이블
    c.execute('''
        CREATE TABLE IF NOT EXISTS pdf_analyses
        (id INTEGER PRIMARY KEY,
         user_id INTEGER,
         filename TEXT,
         analysis_result TEXT,
         created_at TIMESTAMP,
         FOREIGN KEY (user_id) REFERENCES users (id))
    ''')
    
    # 상품 데이터 초기화
    c.execute("SELECT COUNT(*) FROM products")
    if c.fetchone()[0] == 0:  # 상품이 없는 경우에만 추가
        products = [
            ("AI 이미지 생성기", 299000, "고품질 AI 이미지를 생성하는 최신 소프트웨어", "/images/a.jpg"),
            ("데이터 분석 패키지", 199000, "비즈니스 데이터 분석을 위한 종합 패키지", "/images/b.jpg"),
            ("챗봇 빌더 프로", 399000, "맞춤형 AI 챗봇 제작 도구", "/images/c.jpg"),
            ("AI 번역 서비스", 149000, "100개 이상 언어 지원 AI 번역 서비스", "/images/d.jpg"),
            ("머신러닝 스타터킷", 249000, "초보자를 위한 머신러닝 학습 패키지", "/images/e.jpg"),
        ]
        
        c.executemany(
            "INSERT INTO products (name, price, description, image_url) VALUES (?, ?, ?, ?)",
            products
        )
        conn.commit()
    
    conn.close()

# 비밀번호 해시 함수
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# 회원가입
def register_user(username, password, api_key):
    conn = sqlite3.connect('shop.db')
    c = conn.cursor()
    try:
        hashed_password = hash_password(password)
        c.execute(
            "INSERT INTO users (username, password, api_key, created_at) VALUES (?, ?, ?, ?)",
            (username, hashed_password, api_key, datetime.now())
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

# 로그인 검증
def verify_login(username, password):
    conn = sqlite3.connect('shop.db')
    c = conn.cursor()
    hashed_password = hash_password(password)
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, hashed_password))
    user = c.fetchone()
    conn.close()
    return user

# 장바구니 관리
def add_to_cart(user_id, product_id, quantity):
    conn = sqlite3.connect('shop.db')
    c = conn.cursor()
    c.execute(
        "INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, ?)",
        (user_id, product_id, quantity)
    )
    conn.commit()
    conn.close()

def get_cart_items(user_id):
    conn = sqlite3.connect('shop.db')
    c = conn.cursor()
    c.execute("""
        SELECT p.name, p.price, c.quantity, p.id
        FROM cart c
        JOIN products p ON c.product_id = p.id
        WHERE c.user_id = ?
    """, (user_id,))
    items = c.fetchall()
    conn.close()
    return items

# PDF 처리 함수
def process_pdf(pdf_file):
    reader = PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

# PDF 분석 결과 저장
def save_pdf_analysis(user_id, filename, analysis_result):
    conn = sqlite3.connect('shop.db')
    c = conn.cursor()
    c.execute(
        "INSERT INTO pdf_analyses (user_id, filename, analysis_result, created_at) VALUES (?, ?, ?, ?)",
        (user_id, filename, analysis_result, datetime.now())
    )
    conn.commit()
    conn.close()

# 회원가입 페이지
def signup_page():
    st.subheader("회원가입")
    new_username = st.text_input("새로운 사용자명")
    new_password = st.text_input("새로운 비밀번호", type="password")
    new_api_key = st.text_input("Gemini API 키", type="password")
    
    if st.button("회원가입"):
        if register_user(new_username, new_password, new_api_key):
            st.success("회원가입이 완료되었습니다!")
            st.session_state['show_signup'] = False
        else:
            st.error("이미 존재하는 사용자명입니다.")

# 로그인 페이지
def login_page():
    st.title("로그인")
    username = st.text_input("사용자명")
    password = st.text_input("비밀번호", type="password")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("로그인"):
            user = verify_login(username, password)
            if user:
                st.session_state['logged_in'] = True
                st.session_state['user_id'] = user[0]
                st.session_state['username'] = username
                st.session_state['api_key'] = user[3]
                st.success("로그인 성공!")
                st.rerun()
            else:
                st.error("잘못된 로그인 정보입니다.")
    
    with col2:
        if st.button("회원가입"):
            st.session_state['show_signup'] = True

# 상품 페이지
def products_page():
    st.subheader("상품 목록")
    conn = sqlite3.connect('shop.db')
    c = conn.cursor()
    c.execute("SELECT * FROM products")
    products = c.fetchall()
    conn.close()

    # 3열로 상품 표시
    cols = st.columns(3)
    for idx, product in enumerate(products):
        with cols[idx % 3]:
            st.image(product[4], use_column_width=True)
            st.markdown(f"**{product[1]}**")
            st.write(product[3])
            st.write(f"가격: ₩{product[2]:,}")
            if st.button(f"장바구니 담기###{product[0]}", key=f"btn_{product[0]}"):
                add_to_cart(st.session_state['user_id'], product[0], 1)
                st.success("장바구니에 추가되었습니다!")
            st.markdown("---")

# 장바구니 페이지
def cart_page():
    st.subheader("장바구니")
    items = get_cart_items(st.session_state['user_id'])
    
    if not items:
        st.write("장바구니가 비어있습니다.")
        return
    
    total = 0
    for item in items:
        name, price, quantity, product_id = item
        st.write(f"{name} - ₩{price:,.0f} x {quantity}개")
        total += price * quantity
    
    st.write(f"**총액: ₩{total:,.0f}**")
    
    if st.button("결제하기"):
        try:
            # Stripe 결제 세션 생성
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'krw',
                        'product_data': {
                            'name': '장바구니 결제',
                        },
                        'unit_amount': int(total),
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url='http://localhost:8501/success',
                cancel_url='http://localhost:8501/cancel',
            )
            st.write("결제 페이지로 이동합니다...")
            st.markdown(f"<a href='{checkout_session.url}' target='_blank'>결제하기</a>", unsafe_allow_html=True)
        except Exception as e:
            st.error(f"결제 처리 중 오류가 발생했습니다: {str(e)}")

# 메인 애플리케이션
def main():
    st.set_page_config(page_title="AI 쇼핑몰", layout="wide")
    
    # 세션 상태 초기화
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
    if 'show_signup' not in st.session_state:
        st.session_state['show_signup'] = False

    # 데이터베이스 초기화
    init_db()

    # 로그인하지 않은 경우
    if not st.session_state['logged_in']:
        if st.session_state['show_signup']:
            signup_page()
        else:
            login_page()
        return

    # 로그인한 경우
    st.title("AI 쇼핑몰")
    
    # 사이드바 메뉴
    menu = st.sidebar.selectbox(
        "메뉴",
        ["상품 목록", "장바구니", "PDF 분석"]
    )
    
    if menu == "상품 목록":
        products_page()
    elif menu == "장바구니":
        cart_page()
    elif menu == "PDF 분석":
        st.subheader("PDF 분석")
        
        # API 키 확인
        api_key = st.session_state.get('api_key', '')
        if not api_key:
            st.error("API 키가 설정되지 않았습니다.")
            return
            
        genai.configure(api_key=api_key)
        
        # PDF 파일 업로드
        uploaded_file = st.file_uploader("PDF 파일을 업로드하세요", type="pdf")
        
        if uploaded_file:
            text_content = process_pdf(uploaded_file)
            
            # Gemini 모델 설정
            model = genai.GenerativeModel('gemini-pro')
            
            try:
                # PDF 내용 분석
                response = model.generate_content(f"다음 텍스트를 분석해주세요: {text_content[:1000]}")
                st.write("분석 결과:")
                st.write(response.text)
                
                # 분석 결과 저장
                save_pdf_analysis(
                    st.session_state['user_id'],
                    uploaded_file.name,
                    response.text
                )
                st.success("분석 결과가 저장되었습니다.")
            except Exception as e:
                st.error(f"에러가 발생했습니다: {str(e)}")
    
    # 로그아웃 버튼
    if st.sidebar.button("로그아웃"):
        for key in st.session_state.keys():
            del st.session_state[key]
        st.rerun()

if __name__ == "__main__":
    main()
