#!/usr/bin/env python3
"""
Qwen3-TTS 语音克隆测试脚本
支持：语音克隆、自定义音色、语音设计
"""
import os
import sys
import torch
import soundfile as sf

print("=" * 60)
print("Qwen3-TTS 语音克隆测试")
print("=" * 60)

# 配置
MODEL_TYPE = "clone"  # clone / custom / design
MODEL_ID_CLONE = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
MODEL_ID_CUSTOM = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
MODEL_ID_DESIGN = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"

# 本地模型路径（如果已下载）
LOCAL_MODEL_CLONE = "/root/qwen3-tts/models/Qwen3-TTS-12Hz-1.7B-Base"
LOCAL_MODEL_CUSTOM = "/root/qwen3-tts/models/Qwen3-TTS-12Hz-1.7B-CustomVoice"

# 测试参数
REF_AUDIO = "/root/qwen3-tts/ref_audio.wav"  # 参考音频路径
REF_TEXT = "这是一个参考音频，用于克隆声音。"  # 参考音频对应的文本
OUTPUT_DIR = "/root/qwen3-tts/output"
SAMPLE_TEXT = "大学生活是一段美好的时光，在这里我们可以学习知识，结交朋友，参与各种有趣的活动。"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def load_model(model_type="clone"):
    """加载 Qwen3-TTS 模型"""
    from qwen_tts import Qwen3TTSModel
    
    if model_type == "clone":
        model_id = LOCAL_MODEL_CLONE if os.path.exists(LOCAL_MODEL_CLONE) else MODEL_ID_CLONE
        print(f"\n使用模型: 语音克隆 (Base)")
    elif model_type == "custom":
        model_id = LOCAL_MODEL_CUSTOM if os.path.exists(LOCAL_MODEL_CUSTOM) else MODEL_ID_CUSTOM
        print(f"\n使用模型: 自定义音色 (CustomVoice)")
    else:
        model_id = MODEL_ID_DESIGN
        print(f"\n使用模型: 语音设计 (VoiceDesign)")
    
    print(f"模型ID: {model_id}")
    
    print("\n[1/3] 加载模型到 GPU (bfloat16)...")
    print("  首次运行会下载模型，请耐心等待...")
    
    model = Qwen3TTSModel.from_pretrained(
        model_id,
        device_map="cuda",
        dtype=torch.bfloat16,
        attn_implementation="flash_attention_2",  # 需要安装 flash-attn
    )
    
    if torch.cuda.is_available():
        vram = torch.cuda.memory_allocated() / 1e9
        print(f"  模型加载完成! 显存占用: {vram:.2f} GB")
    
    return model

def test_voice_clone(model):
    """测试语音克隆"""
    print("\n[2/3] 测试语音克隆...")
    
    if not os.path.exists(REF_AUDIO):
        print(f"  警告: 参考音频不存在: {REF_AUDIO}")
        print("  将使用内置音色继续测试...")
        return None
    
    print(f"  参考音频: {REF_AUDIO}")
    print(f"  参考文本: {REF_TEXT}")
    
    # 预先创建克隆提示（可复用）
    print("  提取音色特征...")
    try:
        prompt_items = model.create_voice_clone_prompt(
            ref_audio=REF_AUDIO,
            ref_text=REF_TEXT,
        )
        print("  音色特征提取成功!")
    except Exception as e:
        print(f"  提取失败: {e}")
        return None
    
    # 生成音频
    print(f"  生成语音: {SAMPLE_TEXT[:30]}...")
    wavs, sr = model.generate_voice_clone(
        text=SAMPLE_TEXT,
        language="Chinese",
        voice_clone_prompt=prompt_items,
    )
    
    return wavs[0], sr

def test_custom_voice(model):
    """测试自定义音色"""
    print("\n[2/3] 测试自定义音色...")
    
    # 预设音色列表
    speakers = ["Vivian", "Ryan", "Emma", "Alex"]
    speaker = speakers[0]
    
    print(f"  使用音色: {speaker}")
    print(f"  生成语音: {SAMPLE_TEXT[:30]}...")
    
    wavs, sr = model.generate_custom_voice(
        text=SAMPLE_TEXT,
        language="Chinese",
        speaker=speaker,
        instruct="用温柔亲切的语气说",
    )
    
    return wavs[0], sr

def test_voice_design(model):
    """测试语音设计"""
    print("\n[2/3] 测试语音设计...")
    
    instruct = "体现温柔亲切的女声，语速适中，语调柔和"
    
    print(f"  音色描述: {instruct}")
    print(f"  生成语音: {SAMPLE_TEXT[:30]}...")
    
    wavs, sr = model.generate_voice_design(
        text=SAMPLE_TEXT,
        language="Chinese",
        instruct=instruct,
    )
    
    return wavs[0], sr

def main():
    print(f"\n[模式选择] {MODEL_TYPE}")
    print(f"[显存] {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
    
    # 加载模型
    model = load_model(MODEL_TYPE)
    
    # 根据模式测试
    if MODEL_TYPE == "clone":
        result = test_voice_clone(model)
    elif MODEL_TYPE == "custom":
        result = test_custom_voice(model)
    else:
        result = test_voice_design(model)
    
    # 保存结果
    if result:
        audio, sr = result
        output_path = os.path.join(OUTPUT_DIR, f"test_{MODEL_TYPE}.wav")
        sf.write(output_path, audio, sr)
        print(f"\n[3/3] 保存音频: {output_path}")
        print(f"  时长: {len(audio) / sr:.2f} 秒")
        print(f"  采样率: {sr} Hz")
    else:
        print("\n[3/3] 跳过保存（测试未完成）")
    
    # 显存统计
    if torch.cuda.is_available():
        vram = torch.cuda.memory_allocated() / 1e9
        print(f"\n[显存] 最终占用: {vram:.2f} GB")
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)

if __name__ == "__main__":
    main()
