import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import time
from datetime import datetime, timedelta
import os
import re
from collections import Counter
from dotenv import load_dotenv

# Загрузка токена с поддержкой Streamlit Secrets
try:
    # Пытаемся получить токен из Streamlit Secrets (для облака)
    VK_TOKEN = st.secrets["VK_TOKEN"]
except:
    # Если не получилось, пробуем из .env файла (для локальной разработки)
    load_dotenv()
    VK_TOKEN = os.getenv("VK_TOKEN", "")
    
    if not VK_TOKEN:
        st.error("❌ Токен VK не найден! Добавьте VK_TOKEN в Secrets Streamlit или в файл .env")
        st.stop()

st.set_page_config(page_title="Анализатор ННГУ", layout="wide", page_icon="📊")
st.title("🎓 Анализатор активности VK-пабликов")
st.caption("Загрузка данных из VK API | Анализ слов и биграмм | Экспорт в CSV")

# ---------- СТОП-СЛОВА ----------
STOP_WORDS = {
    "и", "в", "на", "с", "по", "не", "что", "как", "это", "для", "от", "у", "к",
    "о", "а", "но", "за", "же", "бы", "то", "все", "всё", "или", "еще", "ещё",
    "уже", "если", "так", "мы", "вы", "он", "она", "они", "его", "ее", "её",
    "их", "нам", "вам", "им", "быть", "есть", "нет", "да", "из", "до", "при",
    "под", "над", "во", "со", "ко", "об", "обо", "перед", "через", "чтобы",
    "когда", "где", "кто", "какой", "который", "наш", "ваш", "свой", "этот",
    "тот", "весь", "один", "два", "три", "год", "время", "также", "более",
    "менее", "очень", "можно", "нужно", "надо", "был", "была", "было", "были",
    "ннгу", "имени", "лобачевского", "университет", "университета"
}

def get_vk_posts(group_id, max_posts=200):
    if not VK_TOKEN:
        return None, "❌ Токен не найден"
    
    # Автоматически добавляем минус, если его нет
    if str(group_id).isdigit():
        group_id = f"-{group_id}"
    
    all_posts = []
    offset = 0
    url = "https://api.vk.com/method/wall.get"
    
    progress_bar = st.progress(0)
    status = st.empty()
    
    try:
        while len(all_posts) < max_posts:
            params = {
                'owner_id': group_id,
                'offset': offset,
                'count': min(100, max_posts - len(all_posts)),
                'access_token': VK_TOKEN,
                'v': '5.131'
            }
            response = requests.get(url, params=params).json()
            
            if 'error' in response:
                return None, f"Ошибка VK: {response['error']['error_msg']}"
            
            posts = response.get('response', {}).get('items', [])
            if not posts:
                break
            
            for post in posts:
                # Извлекаем фото
                photo_url = None
                attachments = post.get('attachments', [])
                for att in attachments:
                    if att.get('type') == 'photo':
                        sizes = att.get('photo', {}).get('sizes', [])
                        if sizes:
                            photo_url = sizes[-1].get('url')
                        break
                
                all_posts.append({
                    'Дата': datetime.fromtimestamp(post['date']).strftime('%Y-%m-%d %H:%M:%S'),
                    'Текст': post['text'][:500] if post['text'] else '',
                    'Лайки': post['likes']['count'],
                    'Комментарии': post['comments']['count'],
                    'Репосты': post['reposts']['count'],
                    'Просмотры': post.get('views', {}).get('count', 0),
                    'Фото': photo_url,
                    'ID поста': post['id']
                })
            
            offset += 100
            progress_bar.progress(min(len(all_posts)/max_posts, 0.99))
            status.text(f"Загружено постов: {len(all_posts)}")
            
            if len(posts) < 100:
                break
            time.sleep(0.34)
        
        progress_bar.progress(1.0)
        status.empty()
        
        df = pd.DataFrame(all_posts)
        if not df.empty:
            df['Дата'] = pd.to_datetime(df['Дата'])
            df['Индекс интереса'] = df['Лайки'] + df['Комментарии'] + df['Репосты']
        
        if len(all_posts) == 0:
            return None, "❌ Постов не найдено. Проверьте ID группы."
        
        return df, f"✅ Загружено {len(df)} постов"
        
    except Exception as e:
        return None, f"❌ Ошибка: {e}"

def get_top_words(texts, top_n=20):
    all_words = []
    for text in texts:
        words = re.findall(r'[а-яё]+', text.lower())
        words = [w for w in words if w not in STOP_WORDS and len(w) > 3]
        all_words.extend(words)
    return Counter(all_words).most_common(top_n)

def get_top_bigrams(texts, top_n=15):
    all_bigrams = []
    for text in texts:
        words = re.findall(r'[а-яё]+', text.lower())
        words = [w for w in words if w not in STOP_WORDS and len(w) > 2]
        for i in range(len(words)-1):
            if words[i] and words[i+1]:
                all_bigrams.append(f"{words[i]} {words[i+1]}")
    return Counter(all_bigrams).most_common(top_n)

# ---------- ИНТЕРФЕЙС ----------
if 'df' not in st.session_state:
    st.session_state.df = None

with st.sidebar:
    st.header("⚙️ Настройки")
    
    group_id = st.text_input("ID группы VK", value="73108225",
                             help="ID группы ННГУ — 73108225")
    
    max_posts = st.slider("Количество постов", 50, 300, 100,
                          help="Чем меньше постов, тем быстрее загрузка")
    
    if st.button("🚀 Загрузить данные", type="primary"):
        with st.spinner("Парсинг VK API..."):
            df, msg = get_vk_posts(group_id, max_posts)
            if df is not None:
                st.session_state.df = df
                st.success(msg)
            else:
                st.error(msg)
    
    st.divider()
    if VK_TOKEN:
        st.success("🔐 Токен VK установлен")
    else:
        st.error("❌ Токен не найден")

# Основной контент
if st.session_state.df is not None:
    df = st.session_state.df
    
    st.success(f"✅ Загружено {len(df)} постов")
    
    # KPI
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📝 Постов", len(df))
    with col2:
        st.metric("❤️ Лайки", f"{df['Лайки'].sum():,}")
    with col3:
        st.metric("💬 Комментарии", f"{df['Комментарии'].sum():,}")
    with col4:
        st.metric("🔄 Репосты", f"{df['Репосты'].sum():,}")
    
    # График динамики
    st.subheader("📈 Динамика активности")
    if len(df) > 1:
        daily = df.groupby(df['Дата'].dt.date).agg({'Лайки': 'sum', 'Комментарии': 'sum'}).reset_index()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=daily['Дата'], y=daily['Лайки'], name='Лайки', line=dict(color='#6366f1')))
        fig.add_trace(go.Scatter(x=daily['Дата'], y=daily['Комментарии'], name='Комментарии', line=dict(color='#10b981')))
        fig.update_layout(template='plotly_dark', height=400)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Недостаточно данных для графика")
    
    # Анализ слов
    st.subheader("📊 Анализ ключевых слов")
    texts = df['Текст'].dropna().astype(str).tolist()
    if texts:
        top_words = get_top_words(texts, 15)
        st.dataframe(pd.DataFrame(top_words, columns=['Слово', 'Частота']), use_container_width=True)
        
        top_bigrams = get_top_bigrams(texts, 10)
        if top_bigrams:
            st.subheader("📎 Устойчивые словосочетания")
            st.dataframe(pd.DataFrame(top_bigrams, columns=['Словосочетание', 'Частота']), use_container_width=True)
    
    # Топ-5 постов
    st.subheader("🏆 Топ-5 лучших постов")
    for _, post in df.nlargest(5, 'Индекс интереса').iterrows():
        with st.expander(f"📌 {post['Дата']} | ❤️ {post['Лайки']} | 💬 {post['Комментарии']}"):
            st.write(post['Текст'][:300] if post['Текст'] else '(нет текста)')
    
    # Экспорт
    st.divider()
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Скачать CSV", csv, "vk_posts.csv", "text/csv")

else:
    st.info("👈 Введите ID группы и нажмите 'Загрузить данные'")
    st.markdown("""
    ### Примеры ID групп:
    - **ННГУ** — 73108225
    - **Я поступаю в ННГУ** — 20277894
    """)

st.caption("📊 Данные загружаются через официальное VK API")