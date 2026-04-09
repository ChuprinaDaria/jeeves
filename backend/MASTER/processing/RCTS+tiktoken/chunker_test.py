from pathlib import Path
from langchain.text_splitter import RecursiveCharacterTextSplitter
import tiktoken, json, re

def clean(text: str) -> str:
    return re.sub(r"[\u200B-\u200D\uFEFF]", "", text.replace("\r\n","\n").replace("\r","\n"))

text = clean(Path("test.txt").read_text(encoding="utf-8"))

# 1) Character-based splitter
char_splitter = RecursiveCharacterTextSplitter(
    separators=["\n\n","\n"," ", ".", ",", "\u200b","\uff0c","\u3001","\uff0e","\u3002",""],
    chunk_size=100,          # 100 characters
    chunk_overlap=20,
    length_function=len,
    is_separator_regex=False,
)

# 2) Token-based splitter
enc = tiktoken.get_encoding("cl100k_base")
def tok_len(s: str) -> int: return len(enc.encode(s))

tok_splitter = RecursiveCharacterTextSplitter(
    separators=["\n\n","\n"," ", ".", ",", "\u200b","\uff0c","\u3001","\uff0e","\u3002",""],
    chunk_size=100,          # 100 tokens now
    chunk_overlap=20,
    length_function=tok_len,
    is_separator_regex=False,
)

# Use split_text to get raw strings, not Document reprs
chunks_char = char_splitter.split_text(text)
chunks_tok  = tok_splitter.split_text(text)

# (Optional) include per-chunk stats so you can *see* the difference
def annotate(chunks):
    return [{"i": i, "chars": len(c), "text": c} for i, c in enumerate(chunks)]

Path("out.json").write_text(json.dumps(annotate(chunks_char), ensure_ascii=False, indent=2), encoding="utf-8")
Path("out1.json").write_text(json.dumps(annotate(chunks_tok), ensure_ascii=False, indent=2), encoding="utf-8")
