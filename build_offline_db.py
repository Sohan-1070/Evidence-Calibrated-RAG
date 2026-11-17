import os
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pathlib import Path

DATA_FOLDER = Path("data")
DB_DIR = DATA_FOLDER / "chroma_db"
PDF_PATH = DATA_FOLDER / "oxford_student_handbook.pdf"

def build_db():
    docs = []

    # Load the main PDF if it exists
    if PDF_PATH.exists():
        print(f"Loading PDF: {PDF_PATH}...")
        loader = PyPDFLoader(str(PDF_PATH))
        docs.extend(loader.load())

    # Automatically load ALL .txt files in the data folder
    txt_files = list(DATA_FOLDER.glob("*.txt"))
    if txt_files:
        for txt_path in txt_files:
            print(f"Loading text: {txt_path.name}...")
            try:
                txt_loader = TextLoader(str(txt_path), encoding="utf-8")
                docs.extend(txt_loader.load())
            except Exception as e:
                print(f"  Warning: could not load {txt_path.name}: {e}")

    if not docs:
        print("No documents found in data folder to index.")
        return

    print(f"\nTotal documents loaded: {len(docs)}")
    print("Splitting into chunks...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(docs)
    print(f"Total chunks created: {len(splits)}")
    print("Creating embeddings and saving to ChromaDB...")
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vectorstore = Chroma.from_documents(
        documents=splits,
        embedding=embeddings,
        persist_directory=str(DB_DIR)
    )
    print(f"\nDone! Offline vector database saved to {DB_DIR}")
    print(f"You can now run ECRAG in Offline Mode and query all loaded documents.")

if __name__ == "__main__":
    build_db()
