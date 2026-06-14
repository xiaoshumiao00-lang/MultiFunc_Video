# API 使用

MultiFunc_Video 提供完整的 Python API，方便集成到你的项目中。

---

## 快速开始

```python
from multifunc_video.service import MultiFuncVideoCore
import asyncio

async def main():
    # 初始化
    multifunc_video = MultiFuncVideoCore()
    await multifunc_video.initialize()
    
    # 生成视频
    result = await multifunc_video.generate_video(
        text="为什么要养成阅读习惯",
        mode="generate",
        n_scenes=5
    )
    
    print(f"视频已生成: {result.video_path}")

# 运行
asyncio.run(main())
```

---

## API 参考

详细 API 文档请查看 [API 概览](../reference/api-overview.md)。

---

## 示例

更多使用示例请参考项目的 `examples/` 目录。

