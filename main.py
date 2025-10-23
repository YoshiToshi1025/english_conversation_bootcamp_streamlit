import streamlit as st
import os
import time
from time import sleep
from pathlib import Path
from streamlit.components.v1 import html
from langchain_classic.memory import ConversationSummaryBufferMemory
from langchain_classic.chains import ConversationChain
from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
)
from langchain_core.messages import SystemMessage
from openai import OpenAI
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import functions as ft
import constants as ct


# 各種設定
load_dotenv()   # .envファイルの読み込み
app_title = ct.APP_NAME + " (ver." + ct.APP_VERSION + ")"    # タイトルにアプリケーション名とバージョンを設定
st.set_page_config(page_title=app_title)    # ページタイトル設定
st.markdown(f"## {app_title}")  # タイトル表示

# 初期設定
if "messages" not in st.session_state:
    st.session_state.messages = []                                                  # ユーザとAIの会話履歴
    st.session_state.qa_messages = []                                               # ユーザとAIのQ&A履歴
    st.session_state.user_input_mode = ""                                           # ユーザの入力モード（音声 or テキスト）
    st.session_state.pre_situation = ""                                             # 前回のシチュエーション
    st.session_state.openai_obj = OpenAI(api_key=os.environ["OPENAI_API_KEY"])      # OpenAIオブジェクト
    st.session_state.llm = ChatOpenAI(model_name="gpt-5-nano", temperature=0.5)    # LLMオブジェクト
    st.session_state.conversation_memory = ConversationSummaryBufferMemory(
        llm=st.session_state.llm,
        max_token_limit=1000,
        return_messages=True
    )                                                                               # 英会話用のメモリ
    st.session_state.evaluation_memory = ConversationSummaryBufferMemory(
        llm=st.session_state.llm,
        max_token_limit=1000,
        return_messages=True
    )                                                                               # 英会話評価用のメモリ
    st.session_state.qa_memory = ConversationSummaryBufferMemory(
        llm=st.session_state.llm,
        max_token_limit=1000,
        return_messages=True
    )                                                                               # 質問回答用のメモリ
    st.session_state.user_input_update_flag = False                                 # ユーザ入力値更新フラグ
    st.session_state.llm_response_evaluation = ""                                   # 英会話評価用のLLM回答

# 左サイドバーの画面設定
with st.sidebar:
    st.markdown("## ⚙️ AI会話設定")
    st.session_state.ai_conversation_setting_situation = st.selectbox("シチュエーション", options=ct.SITUATION_OPTION, label_visibility="visible")
    st.session_state.ai_conversation_setting_conversation_level = st.selectbox("会話レベル", options=ct.CONVERSATION_LEVEL_OPTION, label_visibility="visible")
    st.session_state.ai_conversation_setting_language = st.selectbox("言語", options=ct.LANGUAGE_OPTION, label_visibility="visible")
    st.session_state.ai_conversation_setting_speed_key = st.selectbox("発声速度", options=list(ct.PLAY_SPEED_OPTION.keys()), index=1, label_visibility="visible")
    st.session_state.ai_conversation_setting_speed_value = ct.PLAY_SPEED_OPTION[st.session_state.ai_conversation_setting_speed_key]

    # シチュエーションが変更された場合に会話履歴をリセット
    if st.session_state.pre_situation == "":
        st.session_state.pre_situation = st.session_state.ai_conversation_setting_situation
    elif st.session_state.pre_situation != st.session_state.ai_conversation_setting_situation:
        st.session_state.messages = []
        st.session_state.pre_situation = st.session_state.ai_conversation_setting_situation
        st.session_state.conversation_memory.clear()
        st.session_state.evaluation_memory.clear()
        st.session_state.qa_memory.clear()
        st.rerun()

# 英会話用のChain作成
if "chain_basic_conversation" not in st.session_state or st.session_state.messages == []:
    st.session_state.chain_basic_conversation = ft.create_chain_with_memory(
        ct.SYSTEM_TEMPLATE_BASIC_CONVERSATION.format(
            situation=st.session_state.ai_conversation_setting_situation,
            conversation_level=st.session_state.ai_conversation_setting_conversation_level,
            language=st.session_state.ai_conversation_setting_language
        ), st.session_state.conversation_memory)

# 英会話内容の総合評価用のChain作成
if "chain_overall_evaluation" not in st.session_state or st.session_state.messages == []:
    st.session_state.chain_overall_evaluation = ft.create_chain_with_memory(
        ct.SYSTEM_TEMPLATE_OVERALL_EVALUATION.format(
            situation=st.session_state.ai_conversation_setting_situation,
            conversation_level=st.session_state.ai_conversation_setting_conversation_level,
            language=st.session_state.ai_conversation_setting_language
        ), st.session_state.evaluation_memory)

# 質問回答用のChain作成
if "chain_qa_tutor" not in st.session_state or st.session_state.messages == []:
    st.session_state.chain_qa_tutor = ft.create_chain_with_memory(
        ct.SYSTEM_TEMPLATE_QA_TUTOR.format(
            situation=st.session_state.ai_conversation_setting_situation,
            conversation_level=st.session_state.ai_conversation_setting_conversation_level,
            language=st.session_state.ai_conversation_setting_language
        ), st.session_state.qa_memory)

# タブ定義　    デバッグタブ表示指定がある場合はデバッグタブを表示
if ct.DEBUG_TAB_FLAG:
    conversation_tab, review_tab, qa_tab, debug_tab = st.tabs(["🗣️ AIと英会話", "📜 AIによるアドバイス", "🙋 AIに何でも相談", "🛠️ デバッグ"])
else:
    conversation_tab, review_tab, qa_tab = st.tabs(["🗣️ AIと英会話", "📜 AIによるアドバイス", "🙋 AIに何でも相談"])

# 英会話タブ内の画面設定ーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーー
with conversation_tab:
    st.info("AIと英会話：生成AI相手に音声やテキストで英会話の猛特訓を行うためのアプリです。英語をマスターするまで、繰り返し練習しましょう！",icon="🗣️")

    # 操作説明の表示
    with st.chat_message("assistant", avatar=ct.AI_ICON_PATH):
        st.success("""
            【操作説明】
            - 画面左側の"AI会話設定"欄で、AIとの会話条件を設定します。シチュエーションを変更すると、会話履歴がリセットされます。
            - 「音声で会話」ボタンを押下すると、音声でAIと会話できます。
            - 「テキストで会話」欄に会話文を入力すると、テキストでAIと会話できます。
        """)
    st.divider()

    # ユーザとAIのメッセージ履歴の表示
    for message in st.session_state.messages:
        if message["role"] == "assistant":
            with st.chat_message(message["role"], avatar=ct.AI_ICON_PATH):
                st.markdown(message["content"])
        elif message["role"] == "user":
            with st.chat_message(message["role"], avatar=ct.USER_ICON_PATH):
                st.markdown(message["content"])
        else:
            st.divider()

    # 音声入力またはテキスト入力があった場合の処理
    if st.session_state.messages == []:
        # 最初の会話文を生成して音声読み上げ
        with st.spinner("最初の会話文の生成中..."):
            llm_response = st.session_state.chain_basic_conversation.predict(input="")

            # LLMからの回答を音声データに変換
            llm_response_audio = st.session_state.openai_obj.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=llm_response
            )

            # 一旦mp3形式で音声ファイル作成後、wav形式に変換
            audio_output_file_path = f"{ct.AUDIO_OUTPUT_DIR}/audio_output_{int(time.time())}.wav"
            ft.save_to_wav(llm_response_audio.content, audio_output_file_path)

        # AIメッセージの画面表示とリストへの追加
        with st.chat_message("assistant", avatar=ct.AI_ICON_PATH):
            st.markdown(llm_response)

        # 音声ファイルの読み上げ
        ft.play_wav(audio_output_file_path, speed=st.session_state.ai_conversation_setting_speed_value)

        # LLMからの回答をメッセージ一覧に追加
        st.session_state.messages.append({"role": "assistant", "content": llm_response})

    # 音声入力とテキスト入力のボタン・チャット欄を横並びで表示
    col1, col2 = st.columns([1, 5])

    with col1:
        user_input_voice_flag = st.button("音声で会話", use_container_width=False, type="primary")
    with col2:
        user_input_text = st.chat_input("テキストで会話")

    # ユーザ入力があった場合のユーザー入力モードの設定
    if user_input_voice_flag:
        st.session_state.user_input_mode = "voice"
    elif user_input_text and len(user_input_text.strip()) > 0:
        st.session_state.user_input_mode = "text"
        st.session_state.user_input_text = user_input_text.strip()

    # ユーザ入力モードに応じた処理
    if st.session_state.user_input_mode == "voice":
        # 音声入力モード選択時の処理

        # 音声入力を受け取って音声ファイルを作成
        audio_input_file_path = f"{ct.AUDIO_INPUT_DIR}/audio_input_{int(time.time())}.wav"
        ft.record_audio_on_streamlit(audio_input_file_path)

        # 音声入力ファイルから文字起こしテキストを取得
        with st.spinner('音声入力をテキストに変換中...'):
            transcript = ft.transcribe_audio(audio_input_file_path)
            user_input_text = transcript.text

        # 音声入力テキストの画面表示
        with st.chat_message("user", avatar=ct.USER_ICON_PATH):
            st.markdown(user_input_text)

        with st.spinner("AI会話文の生成中..."):
            # ユーザー入力値をLLMに渡して回答取得
            llm_response = st.session_state.chain_basic_conversation.predict(input=user_input_text)
            
            # LLMからの回答を音声データに変換
            llm_response_audio = st.session_state.openai_obj.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=llm_response
            )

            # 一旦mp3形式で音声ファイル作成後、wav形式に変換
            audio_output_file_path = f"{ct.AUDIO_OUTPUT_DIR}/audio_output_{int(time.time())}.wav"
            ft.save_to_wav(llm_response_audio.content, audio_output_file_path)

        # AIメッセージの画面表示とリストへの追加
        with st.chat_message("assistant", avatar=ct.AI_ICON_PATH):
            st.markdown(llm_response)

        # 音声ファイルの読み上げ
        ft.play_wav(audio_output_file_path, speed=st.session_state.ai_conversation_setting_speed_value)

        # ユーザー入力値とLLMからの回答をメッセージ一覧に追加
        st.session_state.messages.append({"role": "user", "content": user_input_text})
        st.session_state.messages.append({"role": "assistant", "content": llm_response})

        # 処理用フラグのリセット
        st.session_state.user_input_update_flag = True
        st.session_state.user_input_mode = ""

        st.rerun()

    elif st.session_state.user_input_mode == "text":
        # テキスト入力モード選択時の処理

        user_input_text = st.session_state.user_input_text 

        # ユーザー入力テキストの画面表示
        with st.chat_message("user", avatar=ct.USER_ICON_PATH):
            st.markdown(user_input_text)

        # ユーザー入力テキストを音声データに変換
        user_input_audio = st.session_state.openai_obj.audio.speech.create(
            model="tts-1",
            voice="echo",
            input=user_input_text
        )

        # 一旦mp3形式で音声ファイル作成後、wav形式に変換
        audio_output_file_path = f"{ct.AUDIO_OUTPUT_DIR}/audio_output_{int(time.time())}.wav"
        ft.save_to_wav(user_input_audio.content, audio_output_file_path)

        # 音声ファイルの読み上げ
        ft.play_wav(audio_output_file_path, speed=st.session_state.ai_conversation_setting_speed_value)

        #　LLM会話文の生成と読み上げ
        with st.spinner("AI会話文の生成中..."):
            # ユーザー入力値をLLMに渡して回答取得
            llm_response = st.session_state.chain_basic_conversation.predict(input=user_input_text)
            
            # LLMからの回答を音声データに変換
            llm_response_audio = st.session_state.openai_obj.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=llm_response
            )

            # 一旦mp3形式で音声ファイル作成後、wav形式に変換
            audio_output_file_path = f"{ct.AUDIO_OUTPUT_DIR}/audio_output_{int(time.time())}.wav"
            ft.save_to_wav(llm_response_audio.content, audio_output_file_path)

        # AIメッセージの画面表示とリストへの追加
        with st.chat_message("assistant", avatar=ct.AI_ICON_PATH):
            st.markdown(llm_response)

        # 音声ファイルの読み上げ
        ft.play_wav(audio_output_file_path, speed=st.session_state.ai_conversation_setting_speed_value)

        # ユーザー入力値とLLMからの回答をメッセージ一覧に追加
        st.session_state.messages.append({"role": "user", "content": user_input_text})
        st.session_state.messages.append({"role": "assistant", "content": llm_response})

        # 処理用フラグのリセット
        st.session_state.user_input_update_flag = True
        st.session_state.user_input_mode = ""

        st.rerun()

# 評価タブ内の画面設定ーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーー
with review_tab:
    st.info("AIによるアドバイス：あなたの会話内容について、AIによるアドバイスを行います。",icon="📜")

    # メッセージ履歴からユーザーの最後の会話文を取得
    user_input_text = ""
    for message in st.session_state.messages:
        if message["role"] == "user":
            user_input_text = message["content"]

    # ユーザーの最後の会話文が存在する場合に、評価を実行し画面に表示する
    if user_input_text and len(user_input_text.strip()) > 0:
        user_input_text = user_input_text.strip()

        # ユーザメッセージの画面表示
        with st.chat_message("user", avatar=ct.USER_ICON_PATH):
            st.markdown(user_input_text)

        if st.session_state.user_input_update_flag == True:
            with st.spinner("会話内容の分析中..."):
                # ユーザー入力値を英会話評価用LLMに渡して評価結果を取得
                llm_response_evaluation = st.session_state.chain_overall_evaluation.predict(input=user_input_text)
                st.session_state.llm_response_evaluation = llm_response_evaluation
                st.session_state.user_input_update_flag = False

        # AIメッセージの画面表示とリストへの追加
        with st.chat_message("assistant", avatar=ct.AI_ICON_PATH):
            st.markdown(st.session_state.llm_response_evaluation)

# 質問・相談タブ内の画面設定ーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーー
with qa_tab:
    st.info("AIに何でも相談：テキストを入力して、AIに英会話に関連する質問や相談ができます。",icon="🙋")

    # ユーザとAIのメッセージ履歴の表示
    for qa_message in st.session_state.qa_messages:
        if qa_message["role"] == "user":
            with st.chat_message(qa_message["role"], avatar=ct.USER_ICON_PATH):
                st.markdown(qa_message["content"])
        elif qa_message["role"] == "assistant":
            with st.chat_message(qa_message["role"], avatar=ct.AI_ICON_PATH):
                st.markdown(qa_message["content"])

    # ユーザの質問入力欄
    question_text = st.chat_input("英会話に関して知りたいことがあれば、AIに質問してみましょう。")

    # ユーザの質問入力があった場合の処理
    if question_text and len(question_text.strip()) > 0:
        question_text = question_text.strip()

        # ユーザメッセージの画面表示
        with st.chat_message("user", avatar=ct.USER_ICON_PATH):
            st.markdown(question_text)

        with st.spinner("回答の生成中..."):
            # ユーザー入力値をLLMに渡して回答取得
            llm_response_qa = st.session_state.chain_qa_tutor.predict(input=question_text)

        # AIメッセージの画面表示とリストへの追加
        with st.chat_message("assistant", avatar=ct.AI_ICON_PATH):
            st.markdown(llm_response_qa)

        # ユーザー入力値とLLMからの回答をQ&A一覧に追加
        st.session_state.qa_messages.append({"role": "user", "content": question_text})
        st.session_state.qa_messages.append({"role": "assistant", "content": llm_response_qa})

        st.rerun()

# デバッグタブ内の画面設定ーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーー
if ct.DEBUG_TAB_FLAG:
    with debug_tab:
        st.info("デバッグ：アプリの動作確認や問題解決のための情報を表示しています。",icon="🛠️")

        st.info(f"""
            現在のAI会話設定
            - シチュエーション：{st.session_state.ai_conversation_setting_situation}
            - 会話レベル：{st.session_state.ai_conversation_setting_conversation_level}
            - 言語：{st.session_state.ai_conversation_setting_language}
            - 発声速度：{st.session_state.ai_conversation_setting_speed_key}（{st.session_state.ai_conversation_setting_speed_value}倍速）
        """,icon="⚙️")

        st.info(f"{st.session_state}", icon="🛠️",)
