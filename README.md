# Test Bullet - FastAPI Transaction API

Este projeto é uma API simples de transações bancárias feita com FastAPI. A API permite realizar transações de crédito e débito com suporte a chave de idempotência.

## 🚀 Funcionalidades

- Criar transações de crédito ou débito.
- Validação de saldo insuficiente.
- Controle de idempotência.
- Testes automatizados com `pytest` e `httpx`.

## 📦 Requisitos

- Python 3.12
- pip

## 🔧 Instalação

1. Clone o repositório:
   ```bash
   git clone https://github.com/seu-usuario/Test-Bullet.git
   cd Test-Bullet
   ```

2. Crie e ative o ambiente virtual:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   # ou
   .\venv\Scripts\activate  # Windows
   ```

3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

## ▶️ Executando a API

```bash
uvicorn main:app --reload
```

Acesse a documentação interativa em: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## 🧪 Executando os testes

```bash
PYTHONPATH=. pytest
```

## 📝 Exemplo de Requisição

```json
POST /transactions
{
  "idempotencyKey": "abc123",
  "accountId": "acc_001",
  "amount": 100.0,
  "type": "credit",
  "description": "Depósito inicial"
}
```

## 📂 Estrutura do Projeto

```
Test-Bullet/
│
├── main.py                  # Entrada da aplicação FastAPI
├── services.py              # Lógica de negócio
├── storage.py               # Simulação do armazenamento
├── tests/
│   └── test_transactions.py # Testes automatizados
├── requirements.txt         # Dependências
└── README.md                # Instruções do projeto
```

## 📄 Licença

Este projeto está licenciado sob a licença MIT.