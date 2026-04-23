import json
import sys
from pathlib import Path

# 取得檔案路徑
file_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output/composite_v2.json")

# 檢查檔案是否存在
if not file_path.exists():
    print(f"檔案不存在: {file_path}")
    sys.exit(1)

print(f"檔案大小: {file_path.stat().st_size / (1024*1024):.2f} MB")

# 載入 JSON 檔案
with open(file_path, "r", encoding="utf-8") as f:
    try:
        data = json.load(f)
        print(f"資料類型: {type(data)}")
        print(f"資料長度: {len(data)}")

        # 檢查第一個項目
        if data and len(data) > 0:
            first_item = data[0]
            print("\n第一個項目的鍵:")
            for key in first_item.keys():
                print(f"- {key}")

            # 檢查 metadata 是否有 embedding
            if "metadata" in first_item:
                metadata = first_item["metadata"]
                print("\nmetadata 的鍵:")
                for key in metadata.keys():
                    print(f"- {key}")

                # 檢查 embedding
                if "embedding" in metadata:
                    embedding = metadata["embedding"]
                    print(f"\nembedding 類型: {type(embedding)}")
                    print(
                        f"embedding 長度: {len(embedding) if isinstance(embedding, list) else 'not a list'}"
                    )
                    if isinstance(embedding, list) and len(embedding) > 0:
                        print(f"第一個 embedding 值: {embedding[0]}")
                else:
                    print("\nmetadata 中沒有 embedding 欄位")

            # 檢查是否有表格和圖片
            has_table = (
                "table_html" in first_item.get("metadata", {})
                or first_item.get("filetype") == "table/html"
            )
            has_image = (
                "image_base64" in first_item.get("metadata", {})
                or first_item.get("filetype") == "image"
            )

            print(f"\n第一個項目是否為表格: {has_table}")
            print(f"第一個項目是否為圖片: {has_image}")

        # 檢查資料中有多少表格和圖片
        table_count = 0
        image_count = 0
        items_with_embedding = 0

        for item in data:
            metadata = item.get("metadata", {})

            if "embedding" in metadata and metadata["embedding"]:
                items_with_embedding += 1

            if "table_html" in metadata or item.get("filetype") == "table/html":
                table_count += 1

            if "image_base64" in metadata or item.get("filetype") == "image":
                image_count += 1

        print(f"\n資料中的表格數量: {table_count}")
        print(f"資料中的圖片數量: {image_count}")
        print(f"有 embedding 的項目數量: {items_with_embedding}")
        print(f"有 embedding 的項目百分比: {items_with_embedding/len(data)*100:.2f}%")

    except json.JSONDecodeError as e:
        print(f"JSON 解析錯誤: {e}")
