FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8505
CMD ["sh", "-c", "python scripts/bootstrap.py && python -m streamlit run app.py --server.port=8505 --server.address=0.0.0.0"]
