from mcp.server.fastmcp import FastMCP
import os
from datetime import datetime
from typing import List, Dict, Optional
import edge_tts
import asyncio
import nest_asyncio
from mcp.server.fastmcp import FastMCP

nest_asyncio.apply()

# 全局缓存语音管理器
_voice_manager: Optional[edge_tts.VoicesManager] = None
_voice_manager_lock = asyncio.Lock()

server = FastMCP("TTS Server")

# 配置输出目录
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

async def _get_voice_manager() -> edge_tts.VoicesManager:
    """获取语音管理器实例，线程安全"""
    global _voice_manager
    if _voice_manager is None:
        async with _voice_manager_lock:
            if _voice_manager is None:  # 双重检查锁定
                _voice_manager = await edge_tts.VoicesManager.create()
    return _voice_manager

@server.tool(name="list_voice", description="获取可用的语音列表")
def list_voice() -> List[Dict[str, str]]:
    """
    获取可用的语音列表
    
    Returns:
        可用语音列表，每个语音包含ShortName、Gender、Locale等信息，ShortName的值用于选择合适的voice参数
    """
    try:
        voice_manager = asyncio.run(_get_voice_manager())
        return voice_manager.voices
    except Exception as e:
        raise ValueError(f"获取语音列表失败: {str(e)}")

@server.tool(name="tts", description="将文本转换为语音并返回音频文件路径")
def tts(text: str, voice: str, srt_enable: bool = False) -> Dict[str, str]:
    """
    将文本转换为语音并返回音频文件和字幕文件的路径，调用本方法前必须先调用list_voice获取可用的语音列表，根据传入的text参数选择合适的voice参数。
    
    Args:
        text: 要转换为语音的文本 (必须)
        voice: 语音名称，可通过list_voice获取，ShortName的值 (必须)
        srt_enable: 是否生成字幕文件，默认为False
    
    Returns:
        包含音频文件和字幕文件路径的字典
    """
    # 输入验证
    if not text or not text.strip():
        raise ValueError("文本内容不能为空")
    if not voice or not voice.strip():
        raise ValueError("语音名称不能为空")
    
    try:
        # 生成带有时间戳的文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"tts_{timestamp}"
        
        # 设置输出文件路径
        mp3_path = os.path.join(OUTPUT_DIR, f"{filename}.mp3")
        srt_path = os.path.join(OUTPUT_DIR, f"{filename}.srt")
        
        # 使用同步方式生成语音
        communicate = edge_tts.Communicate(text, voice)
        
        # 如果需要生成字幕文件，初始化SubMaker
        submaker = None
        if srt_enable:
            submaker = edge_tts.SubMaker()
        
        # 生成音频文件
        try:
            with open(mp3_path, "wb") as file:
                for chunk in communicate.stream_sync():
                    if chunk["type"] == "audio":
                        file.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary" and submaker:
                        submaker.feed(chunk)
        except Exception as e:
            # 如果生成失败，清理可能创建的文件
            if os.path.exists(mp3_path):
                os.remove(mp3_path)
            raise e
        
        # 如果需要生成字幕文件
        if srt_enable and submaker:
            try:
                with open(srt_path, "w", encoding="utf-8") as srt_file:
                    srt_file.write(submaker.get_srt())
            except Exception as e:
                # 如果字幕生成失败，清理音频文件
                if os.path.exists(mp3_path):
                    os.remove(mp3_path)
                raise e
        
        result = {"audio_path": mp3_path}
        if srt_enable:
            result["subtitle_path"] = srt_path
            
        return result
    except Exception as e:
        raise ValueError(f"TTS转换失败: {str(e)}")

# 通过stdio运行服务器
if __name__ == "__main__":
    server.run()