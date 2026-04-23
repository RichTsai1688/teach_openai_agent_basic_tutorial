#!/usr/bin/env python3
"""
簡單的導入測試腳本，確保從 scripts 目錄可以正確導入 lib 中的模組。
"""
import os
import sys
from pathlib import Path

# 添加 lib 目錄到路徑
current_dir = Path(__file__).parent
lib_dir = current_dir.parent / 'lib'
sys.path.append(str(lib_dir))

# 嘗試導入模組
try:
    from rag_system import RAGSystem
    from composite_element_builder import CompositeElementBuilder
    from composite_element_builder_v2 import CompositeElementBuilder as CompositeElementBuilderV2
    
    print("✅ 成功導入 RAGSystem")
    print("✅ 成功導入 CompositeElementBuilder")
    print("✅ 成功導入 CompositeElementBuilderV2")
    
    # 檢查 embedder.json 文件
    docs_dir = current_dir.parent / 'docs'
    embedder_path = docs_dir / 'embedder.json'
    
    if embedder_path.exists():
        print(f"✅ 找到 embedder.json: {embedder_path}")
    else:
        print(f"❌ 未找到 embedder.json: {embedder_path}")
    
    # 檢查 output 目錄
    output_dir = current_dir.parent / 'output'
    if output_dir.exists() and output_dir.is_dir():
        print(f"✅ 找到 output 目錄: {output_dir}")
        
        # 檢查 output 目錄中的檔案
        json_files = list(output_dir.glob("*.json"))
        if json_files:
            print(f"✅ 在 output 目錄中找到 {len(json_files)} 個 JSON 檔案:")
            for jf in json_files:
                print(f"  - {jf.name}")
        else:
            print("⚠️ output 目錄中沒有 JSON 檔案")
    else:
        print(f"❌ 未找到 output 目錄: {output_dir}")
    
    print("\n✅ 所有模組都已成功導入！測試通過。")
    sys.exit(0)
    
except ImportError as e:
    print(f"❌ 導入錯誤: {e}")
    print(f"當前 sys.path: {sys.path}")
    sys.exit(1)
except Exception as e:
    print(f"❌ 其他錯誤: {e}")
    sys.exit(1)
