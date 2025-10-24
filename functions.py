import streamlit as st
import os
import time
import wave
# from pydub import AudioSegment
from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
)
from langchain_core.messages import SystemMessage
from langchain_classic.chains import ConversationChain
import constants as ct

def record_audio_on_streamlit(audio_input_file_path):
    """
    音声入力を受け取って音声ファイルを作成
    """

    audio_value = st.audio_input("Record a voice message")

    if audio_value:
        st.audio(audio_value, format="audio/wav")
        # 音声データをファイル保存
        audio_data = audio_value.read()
        with open(audio_input_file_path, 'wb') as destination:
            destination.write(audio_data)
    else:
        st.stop()

def transcribe_audio(audio_input_file_path):
    """
    音声入力ファイルから文字起こしテキストを取得
    Args:
        audio_input_file_path: 音声入力ファイルのパス
    """

    with open(audio_input_file_path, 'rb') as audio_input_file:
        transcript = st.session_state.openai_obj.audio.transcriptions.create(
            model="whisper-1",
            file=audio_input_file,
            language="en"
        )
    
    # 音声入力ファイルを削除
    os.remove(audio_input_file_path)

    return transcript

def save_to_wav(llm_response_audio, audio_output_file_path):
    """
    一旦mp3形式で音声ファイル作成後、wav形式に変換
    Args:
        llm_response_audio: LLMからの回答の音声データ
        audio_output_file_path: 出力先のファイルパス
    """

    with open(audio_output_file_path, "wb") as audio_output_file:
        audio_output_file.write(llm_response_audio)

def play_wav(audio_output_file_path, speed=1.0):
    """
    音声ファイルの読み上げ
    Args:
        audio_output_file_path: 音声ファイルのパス
        speed: 再生速度（1.0が通常速度、0.5で半分の速さ、2.0で倍速など）
    """

    # Streamlitで再生
    audio_file = open(audio_output_file_path, 'rb')
    audio_bytes = audio_file.read()
    st.audio(audio_bytes, format='audio/wav', autoplay=True)

    # LLMからの回答の音声ファイルを削除(※直後には削除できない)
    # os.remove(audio_output_file_path)

def create_chain(system_template):
    """
    LLMによる回答生成用のChain作成
    """

    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=system_template),
        MessagesPlaceholder(variable_name="history"),
        HumanMessagePromptTemplate.from_template("{input}")
    ])
    chain = ConversationChain(
        llm=st.session_state.llm,
        memory=st.session_state.memory,
        prompt=prompt
    )

    return chain

def create_chain_with_memory(system_template, the_memory):
    """
    LLMによる回答生成用のChain作成
    """

    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=system_template),
        MessagesPlaceholder(variable_name="history"),
        HumanMessagePromptTemplate.from_template("{input}")
    ])
    chain = ConversationChain(
        llm=st.session_state.llm,
        memory=the_memory,
        prompt=prompt
    )

    return chain

def create_problem_and_play_audio():
    """
    問題生成と音声ファイルの再生
    Args:
        chain: 問題文生成用のChain
        speed: 再生速度（1.0が通常速度、0.5で半分の速さ、2.0で倍速など）
        openai_obj: OpenAIのオブジェクト
    """

    # 問題文を生成するChainを実行し、問題文を取得
    problem = st.session_state.chain_create_problem.predict(input="")

    # LLMからの回答を音声データに変換
    llm_response_audio = st.session_state.openai_obj.audio.speech.create(
        model="tts-1",
        voice="alloy",
        input=problem
    )

    # 音声ファイルの作成
    audio_output_file_path = f"{ct.AUDIO_OUTPUT_DIR}/audio_output_{int(time.time())}.wav"
    save_to_wav(llm_response_audio.content, audio_output_file_path)

    # 音声ファイルの読み上げ
    play_wav(audio_output_file_path, st.session_state.speed)

    return problem, llm_response_audio

def create_evaluation():
    """
    ユーザー入力値の評価生成
    """

    llm_response_evaluation = st.session_state.chain_evaluation.predict(input="")

    return llm_response_evaluation

def is_old_enough(file_path):
    """
    ファイルが一定時間以上前に作成されたかどうかをチェック
    Args:
        file_path: チェックするファイルのパス
        threshold_seconds: 閾値となる時間（秒）
    Returns:
        bool: 一定時間以上前に作成された場合はTrue、そうでない場合はFalse
    """
    file_creation_time = os.path.getctime(file_path)
    current_time = time.time()
    return (current_time - file_creation_time) > ct.AUDIO_TEMP_FILE_THRESHOLD_SECONDS

def clean_audio_temp_dir():
    """
    一時音声ファイル保存ディレクトリのクリーンアップ
    """

    # 一定時間以上前に作成された入力用音声ファイルの削除
    if not os.path.exists(ct.AUDIO_INPUT_DIR):
        os.makedirs(ct.AUDIO_INPUT_DIR)

    for filename in os.listdir(ct.AUDIO_INPUT_DIR):
        file_path = os.path.join(ct.AUDIO_INPUT_DIR, filename)
        try:
            if os.path.isfile(file_path) and is_old_enough(file_path):
                print(f"Deleting file: {file_path}")
                os.remove(file_path)
        except Exception as e:
            print(f"Error deleting file {file_path}: {e}")

    # 出力用音声ファイルの削除
    if not os.path.exists(ct.AUDIO_OUTPUT_DIR):
        os.makedirs(ct.AUDIO_OUTPUT_DIR)

    for filename in os.listdir(ct.AUDIO_OUTPUT_DIR):
        file_path = os.path.join(ct.AUDIO_OUTPUT_DIR, filename)
        try:
            if os.path.isfile(file_path) and is_old_enough(file_path):
                print(f"Deleting file: {file_path}")
                os.remove(file_path)
        except Exception as e:
            print(f"Error deleting file {file_path}: {e}")