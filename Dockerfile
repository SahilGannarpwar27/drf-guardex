FROM python:3.12.3-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY guardex/ .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh
EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
CMD ["gunicorn", "guardex.wsgi:application", "--bind", "0.0.0.0:8000"]