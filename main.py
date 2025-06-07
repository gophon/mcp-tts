from mcp.server.fastmcp import FastMCP
import os
from datetime import datetime
from typing import List, Dict
import edge_tts
import asyncio
import nest_asyncio

nest_asyncio.apply()

server = FastMCP("TTS Server")

# 配置输出目录
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

@server.tool(name="list_voice", description="获取可用的语音列表")
def list_voice() -> List[Dict[str, str]]:
    """
    获取可用的语音列表
    
    Returns:
        可用语音列表，每个语音包含ShortName、Gender、Locale等信息，ShortName的值用于选择合适的voice参数
    """
    try:
        import nest_asyncio
        nest_asyncio.apply()
        manager = asyncio.run(edge_tts.VoicesManager.create())
        return manager.voices
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
        with open(mp3_path, "wb") as file:
            for chunk in communicate.stream_sync():
                if chunk["type"] == "audio":
                    file.write(chunk["data"])
                elif chunk["type"] == "WordBoundary" and submaker:
                    submaker.feed(chunk)
        
        # 如果需要生成字幕文件
        if srt_enable and submaker:
            with open(srt_path, "w", encoding="utf-8") as srt_file:
                srt_file.write(submaker.get_srt())
        
        result = {"audio_path": mp3_path}
        if srt_enable:
            result["subtitle_path"] = srt_path
            
        return result
    except Exception as e:
        raise ValueError(f"TTS转换失败: {str(e)}")

# 通过stdio运行服务器
if __name__ == "__main__":
    server.run()