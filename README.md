
---

# CNPJ API PRIVATE

API privada para **consultas completas de CNPJ**, com autenticação JWT, limites de uso por plano, filtros avançados e cruzamento inteligente de dados empresariais.

---

## 🆕 Cadastro de Usuário

Antes de começar, **registre seu usuário** para obter acesso:

```bash
curl -X POST "http://45.161.137.26:8430/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"seu@email.com","password":"suaSenhaForte123"}'
```

Se o cadastro for bem-sucedido, você receberá uma mensagem de confirmação.

---

## 🔐 Autenticação (Login)

Faça login para receber seu **token JWT** (necessário para todas as consultas):

```bash
curl -X POST "http://45.161.137.26:8430/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"seu@email.com","password":"suaSenhaForte123"}'
```

Resposta de exemplo:

```json
{
  "access_token": "SEU_TOKEN_JWT_AQUI",
  "token_type": "bearer"
}
```

**Inclua o token** em todas as requisições:

```
-H "Authorization: Bearer SEU_TOKEN_JWT_AQUI"
```

---

## 🚦 Limites de Uso

* **Conta gratuita:** 10 requisições por dia
* **Conta limitada:** 3.000 requisições por mês
* **Conta ilimitada:** sem restrições (solicite ao admin)

> ⚠️ **Atenção:** Rotas avançadas (filtros e cruzamentos) exigem conta ativa (`is_active = 1` ou `2`).

---

## 📚 Endpoints Disponíveis

**Troque** `SEU_TOKEN_JWT_AQUI` pelo seu token!

### 1. Buscar dados de um CNPJ específico

```bash
curl -X GET "http://45.161.137.26:8430/api/cnpj/60409075000152" \
  -H "Authorization: Bearer SEU_TOKEN_JWT_AQUI"
```

---

### 2. Listar empresas por UF

```bash
curl -X GET "http://45.161.137.26:8430/api/cnpj/uf/SP?page=1" \
  -H "Authorization: Bearer SEU_TOKEN_JWT_AQUI"
```

---

### 3. Listar empresas por município

```bash
curl -X GET "http://45.161.137.26:8430/api/cnpj/municipio/SAO%20PAULO?page=1" \
  -H "Authorization: Bearer SEU_TOKEN_JWT_AQUI"
```

---

### 4. Listar empresas por CNAE principal

```bash
curl -X GET "http://45.161.137.26:8430/api/cnpj/cnae_principal/1099699?page=1" \
  -H "Authorization: Bearer SEU_TOKEN_JWT_AQUI"
```

---

### 5. Listar empresas por CNAE secundária

```bash
curl -X GET "http://45.161.137.26:8430/api/cnpj/cnae_secundaria/1052000?page=1" \
  -H "Authorization: Bearer SEU_TOKEN_JWT_AQUI"
```

---

### 6. Listar empresas por UF + CNAE principal

```bash
curl -X GET "http://45.161.137.26:8430/api/cnpj/uf/SP/cnae_principal/1099699?page=1" \
  -H "Authorization: Bearer SEU_TOKEN_JWT_AQUI"
```

---

### 7. Listar empresas por UF + CNAE secundária

```bash
curl -X GET "http://45.161.137.26:8430/api/cnpj/uf/SP/cnae_secundaria/1052000?page=1" \
  -H "Authorization: Bearer SEU_TOKEN_JWT_AQUI"
```

---

### 8. Listar empresas por Município + CNAE principal

```bash
curl -X GET "http://45.161.137.26:8430/api/cnpj/municipio/SAO%20PAULO/cnae_principal/1099699?page=1" \
  -H "Authorization: Bearer SEU_TOKEN_JWT_AQUI"
```

---

### 9. Listar empresas por Município + CNAE secundária

```bash
curl -X GET "http://45.161.137.26:8430/api/cnpj/municipio/SAO%20PAULO/cnae_secundaria/1052000?page=1" \
  -H "Authorization: Bearer SEU_TOKEN_JWT_AQUI"
```

---

## 🔗 Rotas de Cruzamento & Relacionamentos

> **⚠️ Acesso restrito:** apenas para usuários ativos (`is_active = 1` ou `2`).

### 10. CNPJs com **mesmo endereço**

```bash
curl -X GET "http://45.161.137.26:8430/api/cruzamentos/enderecos/compartilhados?endereco=RUA%20X" \
  -H "Authorization: Bearer SEU_TOKEN_JWT_AQUI"
```

### 11. CNPJs com **mesmo e-mail**

```bash
curl -X GET "http://45.161.137.26:8430/api/cruzamentos/emails/compartilhados?email=EXEMPLO@MAIL.COM" \
  -H "Authorization: Bearer SEU_TOKEN_JWT_AQUI"
```

### 12. CNPJs com **mesmo telefone**

```bash
curl -X GET "http://45.161.137.26:8430/api/cruzamentos/telefones/compartilhados?ddd=11&telefone=12345678" \
  -H "Authorization: Bearer SEU_TOKEN_JWT_AQUI"
```

### 13. Listar **endereços** duplicados (usados por mais de um CNPJ)

```bash
curl -X GET "http://45.161.137.26:8430/api/cruzamentos/enderecos/duplicados?minimo=2" \
  -H "Authorization: Bearer SEU_TOKEN_JWT_AQUI"
```

### 14. Listar **telefones** duplicados

```bash
curl -X GET "http://45.161.137.26:8430/api/cruzamentos/telefones/duplicados?minimo=2" \
  -H "Authorization: Bearer SEU_TOKEN_JWT_AQUI"
```

### 15. Listar **e-mails** duplicados

```bash
curl -X GET "http://45.161.137.26:8430/api/cruzamentos/emails/duplicados?minimo=2" \
  -H "Authorization: Bearer SEU_TOKEN_JWT_AQUI"
```

### 16. Buscar **todos os vínculos** (endereços, e-mails, telefones) de um CNPJ

```bash
curl -X GET "http://45.161.137.26:8430/api/cruzamentos/vinculos/60409075000152" \
  -H "Authorization: Bearer SEU_TOKEN_JWT_AQUI"
```

### 17. Buscar **rede de relacionamentos** do CNPJ

```bash
curl -X GET "http://45.161.137.26:8430/api/cruzamentos/rede/60409075000152" \
  -H "Authorization: Bearer SEU_TOKEN_JWT_AQUI"
```

### 18. Análise de **grupo econômico** do CNPJ

```bash
curl -X GET "http://45.161.137.26:8430/api/cruzamentos/analise/grupo_economico/60409075000152" \
  -H "Authorization: Bearer SEU_TOKEN_JWT_AQUI"
```

---

## 🛡️ Segurança & Política de Acesso

* **Todas as rotas exigem autenticação JWT.**
* Cruzamentos e consultas avançadas **exigem plano ativo**.
* O uso abusivo pode gerar bloqueio automático do usuário.
* Alterações de privilégio (`is_active`) apenas por administradores via painel/admin API.

---

## ℹ️ Sobre

* **Base de dados:** Receita Federal + tabelas auxiliares + cruzamentos inteligentes.
* **Formato das respostas:** JSON estruturado, incluindo empresa, sócios, contatos e rede de vínculos.
* **Administração:** Gerencie usuários e privilégios pelo painel admin seguro (Streamlit).

---

**Dúvidas, bugs ou sugestão?**
Abra um *issue* ou contate o responsável pelo sistema.

---
