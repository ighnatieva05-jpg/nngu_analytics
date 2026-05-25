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

# Загрузка токена с поддержкой Streamlit Cloud Secrets
try:
    # Пытаемся получить токен из Streamlit Secrets (для облака)
    VK_TOKEN = st.secrets["VK_TOKEN"]
except:
    # Если не получилось, пробуем из .env файла (для локальной разработки)
    from dotenv import load_dotenv
    load_dotenv()
    VK_TOKEN = os.getenv("VK_TOKEN", "")
    
    if not VK_TOKEN:
        st.error("❌ Токен VK не найден! Добавьте VK_TOKEN в Secrets Streamlit или в файл .env")
        st.stop()

st.set_page_config(page_title="Анализатор ННГУ | Сравнение групп", layout="wide", page_icon="📊")
st.title("🎓 Анализатор активности VK-пабликов")
st.caption("Загрузка данных из VK API | Анализ слов и биграмм | Сравнение групп | Экспорт в CSV")

# ---------- РАСШИРЕННЫЙ СПИСОК СТОП-СЛОВ ----------
STOP_WORDS = {
    "и", "в", "на", "с", "по", "не", "что", "как", "это", "для", "от", "у", "к",
    "о", "а", "но", "за", "же", "бы", "то", "все", "всё", "или", "еще", "ещё",
    "уже", "если", "так", "мы", "вы", "он", "она", "они", "его", "ее", "её",
    "их", "нам", "вам", "им", "быть", "есть", "нет", "да", "из", "до", "при",
    "под", "над", "во", "со", "ко", "об", "обо", "перед", "через", "чтобы",
    "когда", "где", "кто", "какой", "который", "наш", "ваш", "свой", "этот",
    "тот", "весь", "один", "два", "три", "год", "время", "также", "более",
    "менее", "очень", "можно", "нужно", "надо", "был", "была", "было", "были",
    "я", "ты", "он", "она", "оно", "мы", "вы", "они", "себя", "мне", "тебе",
    "себе", "меня", "тебя", "нас", "вас", "их", "мной", "тобой", "собой",
    "проходить", "итог", "приглашать", "образовательный", "летие", "директор",
    "пусть", "основа", "помочь", "настоящий", "топ", "руководитель", "открыть",
    "встреча", "эксперт", "вопрос", "команда", "коллега", "школьник", "дело",
    "число", "делать", "университетский", "смотреть", "нами", "вами", "ими",
    "мочь", "сказать", "преподаватель", "важный", "март", "главный", "решение",
    "дверь", "технология", "рассказать", "учебный", "всероссийский", "регион",
    "российский", "знать", "думать", "говорить", "ннгу", "имени", "отметить",
    "направление", "открытый", "другой", "студенческий", "программа", "мир",
    "кафедра", "курс", "поздравлять", "хороший", "рамка", "факультет", "большой",
    "праздник", "человек", "ребёнок", "лоб", "россии", "области", "году", "года",
    "будет", "всех", "ннг", "научный", "область", "ребенок", "представить",
    "новый", "высокий", "состояться", "работать", "нижний", "страна", "сегодня",
    "только", "место", "рамках", "лет", "день", "октября", "марта", "новгород",
    "октябрь", "каждый", "система", "центр", "нижегородской", "университета",
    "университет", "института", "институт", "самый", "стать", "ждать", "такой",
    "получить", "пройти", "проекта", "проект", "наши", "которые", "этом",
    "вместе", "работы", "развития", "поддержке", "поздравляем", "первый",
    "свои", "просто", "факультета", "науки", "участие", "дня", "чем", "жизни",
    "будут", "мира", "среди", "них", "александр", "стал", "дверей", "всегда",
    "больше", "сейчас", "без", "вузов", "учёные", "новгороде", "нижнем",
    "регистрация", "оба", "иностранный", "известный", "почетный", "формироваться",
    "наталья", "григорьев", "трофим", "глобальный", "агрегированный", "широкий",
    "спектр", "показатель", "оценивать", "заведение", "база", "начало", "признание",
    "желать", "участников", "рейтинг", "будущий", "уникальный", "специалист",
    "лобачевского", "имомь", "данные", "вот", "слово", "яркий", "подробность",
    "войти", "после", "олег", "региональный", "филиал", "огромный", "приходить",
    "вид", "город", "обучаться", "профессиональный", "ребята"
}

def get_vk_posts(group_id, max_posts=200):
    """Загружает посты из VK (максимум max_posts постов)"""
    if not VK_TOKEN:
        return None, "❌ Токен не найден"
    
    all_posts = []
    offset = 0
    url = "https://api.vk.com/method/wall.get"
    
    progress_bar = st.progress(0)
    status = st.empty()
    
    try:
        while len(all_posts) < max_posts:
            params = {
                'owner_id': f'-{group_id}',
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
                # Извлекаем фото (если есть)
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
        
        return df, f"✅ Загружено {len(df)} постов"
        
    except Exception as e:
        return None, f"❌ Ошибка: {e}"

def get_group_info(group_id):
    if not VK_TOKEN:
        return "Группа", 0
    
    url = "https://api.vk.com/method/groups.getById"
    params = {
        'group_id': group_id,
        'access_token': VK_TOKEN,
        'v': '5.131'
    }
    try:
        response = requests.get(url, params=params).json()
        group = response.get('response', [{}])[0]
        return group.get('name', 'Группа'), group.get('members_count', 0)
    except:
        return "Группа", 0

def get_top_words(texts, top_n=20):
    """Извлекает топ-слова из текстов"""
    all_words = []
    for text in texts:
        words = re.findall(r'[а-яё]+', text.lower())
        words = [w for w in words if w not in STOP_WORDS and len(w) > 3]
        all_words.extend(words)
    return Counter(all_words).most_common(top_n)

def get_top_bigrams(texts, top_n=15):
    """Извлекает топ-биграммы (пары слов) из текстов"""
    all_bigrams = []
    for text in texts:
        words = re.findall(r'[а-яё]+', text.lower())
        words = [w for w in words if w not in STOP_WORDS and len(w) > 2]
        for i in range(len(words)-1):
            if words[i] and words[i+1]:
                all_bigrams.append(f"{words[i]} {words[i+1]}")
    return Counter(all_bigrams).most_common(top_n)

# Инициализация данных в сессии
if 'df1' not in st.session_state:
    st.session_state.df1 = None
    st.session_state.df2 = None
    st.session_state.name1 = "Группа 1"
    st.session_state.name2 = "Группа 2"
    st.session_state.mode = "single"

# Боковая панель
with st.sidebar:
    st.header("⚙️ Настройки")
    
    # Выбор режима: одна группа или сравнение
    mode = st.radio("Режим анализа", ["📊 Одна группа", "⚔️ Сравнение двух групп"])
    st.session_state.mode = mode
    
    if mode == "📊 Одна группа":
        group_id = st.text_input("ID группы VK", value="73108225",
                                 help="ID группы ННГУ — 73108225")
        max_posts = st.slider("Количество постов", 50, 500, 200,
                              help="Чем больше постов, тем дольше загрузка")
        
        if st.button("🚀 Загрузить данные", type="primary"):
            with st.spinner("Парсинг VK API..."):
                df, msg = get_vk_posts(group_id, max_posts)
                st.session_state.df1 = df
                st.session_state.df2 = None
                st.session_state.msg = msg
                
                if df is not None:
                    group_name, _ = get_group_info(group_id)
                    st.session_state.name1 = group_name
                    st.session_state.current_group_id = group_id
        
    else:  # Режим сравнения
        st.subheader("Группа 1")
        group_id1 = st.text_input("ID группы 1", value="73108225", key="g1")
        max_posts1 = st.slider("Постов для группы 1", 50, 300, 150, key="m1")
        
        st.subheader("Группа 2")
        group_id2 = st.text_input("ID группы 2", value="20277894", key="g2")
        max_posts2 = st.slider("Постов для группы 2", 50, 300, 150, key="m2")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📥 Загрузить группу 1", key="load1"):
                with st.spinner("Загрузка группы 1..."):
                    df, msg = get_vk_posts(group_id1, max_posts1)
                    if df is not None:
                        st.session_state.df1 = df
                        name, _ = get_group_info(group_id1)
                        st.session_state.name1 = name
                        st.success(f"✅ {name} загружена")
        with col2:
            if st.button("📥 Загрузить группу 2", key="load2"):
                with st.spinner("Загрузка группы 2..."):
                    df, msg = get_vk_posts(group_id2, max_posts2)
                    if df is not None:
                        st.session_state.df2 = df
                        name, _ = get_group_info(group_id2)
                        st.session_state.name2 = name
                        st.success(f"✅ {name} загружена")
    
    st.divider()
    
    if VK_TOKEN:
        st.success("🔐 Токен VK установлен")
    else:
        st.error("❌ Токен не найден")

# ---------- ОСНОВНОЙ КОНТЕНТ ----------

if st.session_state.mode == "📊 Одна группа":
    # Режим одной группы
    if st.session_state.df1 is not None:
        df = st.session_state.df1
        group_id = st.session_state.get('current_group_id', '73108225')
        
        st.success(f"✅ {st.session_state.name1} — загружено {len(df)} постов")
        
        # KPI карточки
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("📝 Всего постов", len(df))
        with col2:
            st.metric("❤️ Лайки", f"{df['Лайки'].sum():,}")
        with col3:
            st.metric("💬 Комментарии", f"{df['Комментарии'].sum():,}")
        with col4:
            st.metric("🔄 Репосты", f"{df['Репосты'].sum():,}")
        with col5:
            st.metric("👁️ Просмотры", f"{df['Просмотры'].sum():,}")
        
        # График динамики
        st.subheader("📈 Динамика активности по дням")
        daily = df.groupby(df['Дата'].dt.date).agg({
            'Лайки': 'sum',
            'Комментарии': 'sum',
            'Репосты': 'sum'
        }).reset_index()
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=daily['Дата'], y=daily['Лайки'], name='Лайки', line=dict(color='#6366f1', width=2)))
        fig.add_trace(go.Scatter(x=daily['Дата'], y=daily['Комментарии'], name='Комментарии', line=dict(color='#10b981', width=2)))
        fig.add_trace(go.Scatter(x=daily['Дата'], y=daily['Репосты'], name='Репосты', line=dict(color='#f59e0b', width=2)))
        fig.update_layout(template='plotly_dark', height=450, hovermode='x unified')
        st.plotly_chart(fig, use_container_width=True)
        
        # Анализ слов и биграмм
        st.subheader("📊 Анализ ключевых слов и тем")
        
        texts = df['Текст'].dropna().astype(str).tolist()
        top_words = get_top_words(texts, 20)
        top_bigrams = get_top_bigrams(texts, 15)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**🏆 Топ-20 самых частых слов**")
            word_df = pd.DataFrame(top_words, columns=['Слово', 'Частота'])
            st.dataframe(word_df, use_container_width=True, hide_index=True)
            
            st.markdown("**☁️ Облако слов**")
            if top_words:
                max_count = top_words[0][1]
                cloud_html = "<div style='display: flex; flex-wrap: wrap; gap: 8px; padding: 10px 0;'>"
                for word, count in top_words[:30]:
                    size = 12 + (count / max_count) * 28
                    color = f"hsl({200 + (count / max_count) * 100}, 70%, 55%)"
                    cloud_html += f"<span style='font-size: {size:.0f}px; color: {color}; margin: 5px; display: inline-block;'>{word}</span>"
                cloud_html += "</div>"
                st.markdown(cloud_html, unsafe_allow_html=True)
        
        with col2:
            st.markdown("**📎 Топ-15 устойчивых словосочетаний (биграммы)**")
            bigram_df = pd.DataFrame(top_bigrams, columns=['Словосочетание', 'Частота'])
            st.dataframe(bigram_df, use_container_width=True, hide_index=True)
            
            if top_bigrams:
                fig_bigrams = px.bar(bigram_df, x='Частота', y='Словосочетание', orientation='h',
                                      title='Самые частые пары слов',
                                      labels={'Частота': 'Сколько раз встретилось', 'Словосочетание': ''},
                                      template='plotly_dark', color='Частота',
                                      color_continuous_scale='Viridis')
                fig_bigrams.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
                st.plotly_chart(fig_bigrams, use_container_width=True)
        
        # Топ-5 лучших постов
        st.subheader("🏆 Топ-5 лучших постов по вовлечённости")
        top_posts = df.nlargest(5, 'Индекс интереса')
        
        for idx, post in top_posts.iterrows():
            post_date = post['Дата'].strftime('%d.%m.%Y %H:%M') if hasattr(post['Дата'], 'strftime') else str(post['Дата'])[:16]
            header = f"📌 {post_date} | ❤️ {post['Лайки']} | 💬 {post['Комментарии']} | 🔄 {post['Репосты']}"
            
            with st.expander(header):
                col_text, col_photo = st.columns([3, 1])
                with col_text:
                    post_text = post['Текст'] if post['Текст'] and len(str(post['Текст'])) > 10 else '(текст отсутствует)'
                    st.write(post_text)
                    group_id_clean = group_id.replace('-', '')
                    post_link = f"https://vk.com/wall-{group_id_clean}_{post['ID поста']}"
                    st.caption(f"[🔗 Открыть пост в VK]({post_link})")
                with col_photo:
                    if pd.notna(post.get('Фото')) and post.get('Фото'):
                        st.image(post['Фото'], use_container_width=True)
                    else:
                        st.caption("📷 фото отсутствует")
        
        # Экспорт
        st.divider()
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Скачать данные в CSV", csv, f"vk_posts_{group_id}.csv", "text/csv")
    
    else:
        st.info("👈 Введите ID группы и нажмите 'Загрузить данные'")
        st.markdown("""
        ### Примеры ID групп:
        - **ННГУ** — 73108225
        - **Я поступаю в ННГУ** — 20277894
        """)

else:
    # РЕЖИМ СРАВНЕНИЯ
    st.header("⚔️ Сравнительный анализ двух групп")
    
    if st.session_state.df1 is not None and st.session_state.df2 is not None:
        df1 = st.session_state.df1
        df2 = st.session_state.df2
        name1 = st.session_state.name1
        name2 = st.session_state.name2
        
        # KPI в 2 ряда
        st.subheader("📊 Сравнение показателей")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric(f"📝 {name1} — постов", len(df1))
            st.metric(f"❤️ {name1} — лайков", f"{df1['Лайки'].sum():,}")
            st.metric(f"💬 {name1} — комментариев", f"{df1['Комментарии'].sum():,}")
        with col2:
            st.metric(f"📝 {name2} — постов", len(df2))
            st.metric(f"❤️ {name2} — лайков", f"{df2['Лайки'].sum():,}")
            st.metric(f"💬 {name2} — комментариев", f"{df2['Комментарии'].sum():,}")
        
        # График сравнения лайков
        st.subheader("📈 Сравнение динамики лайков")
        daily1 = df1.groupby(df1['Дата'].dt.date)['Лайки'].sum().reset_index()
        daily2 = df2.groupby(df2['Дата'].dt.date)['Лайки'].sum().reset_index()
        
        fig_compare = go.Figure()
        fig_compare.add_trace(go.Scatter(x=daily1['Дата'], y=daily1['Лайки'], name=name1, line=dict(color='#6366f1', width=2)))
        fig_compare.add_trace(go.Scatter(x=daily2['Дата'], y=daily2['Лайки'], name=name2, line=dict(color='#f59e0b', width=2)))
        fig_compare.update_layout(template='plotly_dark', height=450, title="Сравнение активности")
        st.plotly_chart(fig_compare, use_container_width=True)
        
        # Сравнение типов контента
        st.subheader("📸 Сравнение вовлечённости")
        
        def get_content_type(text):
            text = str(text).lower()
            if "видео" in text or "youtube" in text:
                return "Видео"
            elif "опрос" in text or "голосование" in text:
                return "Опрос"
            elif "фото" in text or "снимок" in text:
                return "Фото"
            else:
                return "Текст"
        
        df1['Тип'] = df1['Текст'].apply(get_content_type)
        df2['Тип'] = df2['Текст'].apply(get_content_type)
        
        type_eng1 = df1.groupby('Тип')['Индекс интереса'].mean().reset_index()
        type_eng2 = df2.groupby('Тип')['Индекс интереса'].mean().reset_index()
        type_eng1.columns = ['Тип', name1]
        type_eng2.columns = ['Тип', name2]
        
        type_compare = pd.merge(type_eng1, type_eng2, on='Тип', how='outer').fillna(0)
        st.dataframe(type_compare, use_container_width=True)
        
        # Сравнение топ-слов
        st.subheader("🏆 Сравнение ключевых слов")
        texts1 = df1['Текст'].dropna().astype(str).tolist()
        texts2 = df2['Текст'].dropna().astype(str).tolist()
        
        top1 = dict(get_top_words(texts1, 10))
        top2 = dict(get_top_words(texts2, 10))
        
        words_compare = pd.DataFrame({
            f'Топ-10 {name1}': list(top1.keys()),
            'Частота 1': list(top1.values()),
            f'Топ-10 {name2}': list(top2.keys()),
            'Частота 2': list(top2.values())
        })
        st.dataframe(words_compare, use_container_width=True)
        
        # Экспорт CSV для обеих групп
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            csv1 = df1.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Скачать CSV группы 1", csv1, f"{name1}.csv", "text/csv")
        with col2:
            csv2 = df2.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Скачать CSV группы 2", csv2, f"{name2}.csv", "text/csv")
    
    else:
        st.info("👈 Загрузите две группы для сравнения")
        st.markdown("""
        ### Как сравнить группы:
        1. Выберите **"⚔️ Сравнение двух групп"** в боковой панели
        2. Введите ID первой группы (например, ННГУ — 73108225)
        3. Нажмите **"📥 Загрузить группу 1"**
        4. Введите ID второй группы (например, 20277894)
        5. Нажмите **"📥 Загрузить группу 2"**
        """)

st.caption("📊 Данные загружаются через официальное VK API. Режим сравнения позволяет анализировать две группы одновременно.")