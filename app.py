import streamlit as st
import os
from google import genai
from PIL import Image
from docx import Document
from docx.shared import Inches
import io
import socket
import qrcode

# 1. API 키 설정
API_KEY = "AQ.Ab8RN6JeD7GDknfM9jFK3SNq7eMlc0iKMp8pEAk9NZLgw17wzA"
client = genai.Client(api_key=API_KEY)

# --- 도우미 함수 모음 ---
def get_local_ip():
    """현재 작동 중인 PC의 내부 IP 주소를 가져옵니다."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def get_sort_key(file):
    name = os.path.splitext(file.name)[0]
    try:
        return int(name) 
    except ValueError:
        return name 

def analyze_image_to_structured_data(image):
    prompt = """
    이 이미지에 있는 영어 독해 지문을 처음부터 끝까지 빠짐없이 '문장 단위'로 분석해줘.
    결과를 워드 파일 표에 넣을 거니까, 반드시 아래의 양식을 엄격하게 지켜서 작성해.
    문장 하나 분석이 끝날 때마다 반드시 '====' 기호를 넣어서 구분해줘.
    
    [EN] (여기에 영어 원문 문장)
    [KO] (여기에 한국어 전체 해석)
    [CHUNK] (여기에 끊어 읽기 분석, 예: I go / to school -> 나는 간다 / 학교에)
    [VOCAB] (단어1: 뜻, 단어2: 뜻 - 어려운 단어가 없으면 '없음'이라고 적을 것)
    ====
    """
    
    # 구글 공식 SDK 표준 방식 (PIL Image와 프롬프트를 리스트로 전달)
    response = client.models.generate_content(
        model='gemini-1.5-flash',
        contents=[image, prompt],
    )
    return response.text

def parse_blocks_to_data(analyzed_blocks_list):
    parsed_data = []
    for blocks in analyzed_blocks_list:
        for block in blocks.split('===='):
            if not block.strip():
                continue
            
            en_text, ko_text, chunk_text, vocab_text = "", "", "", ""
            
            for line in block.strip().split('\n'):
                line = line.strip()
                if line.startswith('[EN]'): en_text = line.replace('[EN]', '').strip()
                elif line.startswith('[KO]'): ko_text = line.replace('[KO]', '').strip()
                elif line.startswith('[CHUNK]'): chunk_text = line.replace('[CHUNK]', '').strip()
                elif line.startswith('[VOCAB]'): vocab_text = line.replace('[VOCAB]', '').strip()
            
            if en_text:
                parsed_data.append({
                    "en": en_text,
                    "ko": ko_text,
                    "chunk": chunk_text,
                    "vocab": vocab_text
                })
    return parsed_data

def create_word_document(parsed_data):
    doc = Document()
    doc.add_heading('📚 맞춤형 독해 분석 결과', 0)
    
    table = doc.add_table(rows=1, cols=2)
    table.style = 'Table Grid'
    
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = '원문 (English)'
    hdr_cells[1].text = '분석 (Translation & Vocab)'
    
    for item in parsed_data:
        row_cells = table.add_row().cells
        row_cells[0].text = item['en']
        row_cells[1].text = f"[해석]\n{item['ko']}\n\n[끊어 읽기]\n{item['chunk']}\n\n[단어]\n{item['vocab']}"
                
    doc_io = io.BytesIO()
    doc.save(doc_io)
    doc_io.seek(0)
    return doc_io

# --- Streamlit UI ---
st.set_page_config(layout="wide")

with st.sidebar:
    st.markdown("### 📱 스마트폰으로 사진 찍기")
    local_ip = get_local_ip()
    local_url = f"http://{local_ip}:8501"
    
    qr = qrcode.make(local_url)
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    buf.seek(0)
    
    st.image(buf, caption="스마트폰 기본 카메라로 스캔하세요")

st.title("📚 사랑하는 욘다를 위한 아빠의 선물")

if 'parsed_data' not in st.session_state:
    st.session_state.parsed_data = None
if 'word_file' not in st.session_state:
    st.session_state.word_file = None

uploaded_files = st.file_uploader("이미지 파일(jpg, png 등)을 업로드하거나 스마트폰으로 접속해 사진을 찍으세요. (여러 장 가능)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

if uploaded_files:
    uploaded_files.sort(key=get_sort_key)
    st.info(f"총 {len(uploaded_files)}장의 이미지가 업로드되었습니다. 파일명(또는 촬영) 순서대로 분석을 시작합니다.")
    
    if st.button("문장 분석 및 워드 파일 생성"):
        all_analyzed_blocks = []
        
        for idx, file in enumerate(uploaded_files):
            with st.spinner(f"[{idx+1}/{len(uploaded_files)}] '{file.name}' 이미지를 분석 중입니다..."):
                image = Image.open(file)
                analyzed_result = analyze_image_to_structured_data(image)
                all_analyzed_blocks.append(analyzed_result)
        
        st.session_state.parsed_data = parse_blocks_to_data(all_analyzed_blocks)
        st.session_state.word_file = create_word_document(st.session_state.parsed_data)

if st.session_state.parsed_data:
    st.success("✅ 문서 생성이 완료되었습니다! 아래에서 내용을 확인하세요.")
    
    st.download_button(
        label="📥 분석된 워드 문서(.docx) 다운로드",
        data=st.session_state.word_file,
        file_name="독해분석결과.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    
    st.subheader("👀 분석 결과 미리보기")
    
    header_col1, header_col2 = st.columns(2)
    with header_col1:
        st.markdown("### 📖 원문 (English)")
    with header_col2:
        st.markdown("### 📝 분석 (Translation & Vocab)")
    st.divider()
    
    for item in st.session_state.parsed_data:
        col1, col2 = st.columns(2)
        with col1:
            st.write(item['en'])
        with col2:
            st.markdown(f"**[해석]** {item['ko']}")
            st.markdown(f"**[끊어 읽기]** {item['chunk']}")
            st.markdown(f"**[단어]** {item['vocab']}")
        st.divider()
