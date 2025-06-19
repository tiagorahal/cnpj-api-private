

# CNPJ API PRIVATE

API privada para consultas completas de CNPJ com autenticação JWT, controle de limites, filtros avançados e cruzamento de dados.

---

## 🆕 Cadastro de Usuário

Antes de tudo, crie um usuário para receber acesso:

```bash
curl -X POST "http://45.161.137.26:8430/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"seu@email.com","password":"suaSenhaForte123"}'
````

Se o cadastro for bem-sucedido, você receberá uma mensagem de confirmação.

---

## 🔐 Autenticação (Login)

Obtenha seu **token de acesso** (necessário para todas as consultas):

```bash
curl -X POST "http://45.161.137.26:8430/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"seu@email.com","password":"suaSenhaForte123"}'
```

Resposta exemplo:

```json
{
  "access_token": "SEU_TOKEN_JWT_AQUI",
  "token_type": "bearer"
}
```

Inclua sempre o token nas requisições:

```
-H "Authorization: Bearer SEU_TOKEN_JWT_AQUI"
```

---

## 🚦 Limites de Uso

* **Conta gratuita:** 10 requisições por dia
* **Conta limitada:** 3.000 requisições por mês
* **Conta ilimitada:** sem restrição (consultar admin)

**Obs:** Rotas avançadas (filtros e cruzamentos) exigem conta ativa (`is_active = 1` ou `2`).

---

## 📚 Rotas Disponíveis e Exemplos

> **Troque SEU\_TOKEN\_JWT\_AQUI pelo token recebido no login!**

---

### 1. Buscar CNPJ específico

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

### 6. Listar por UF + CNAE principal

```bash
curl -X GET "http://45.161.137.26:8430/api/cnpj/uf/SP/cnae_principal/1099699?page=1" \
  -H "Authorization: Bearer SEU_TOKEN_JWT_AQUI"
```

---

### 7. Listar por UF + CNAE secundária

```bash
curl -X GET "http://45.161.137.26:8430/api/cnpj/uf/SP/cnae_secundaria/1052000?page=1" \
  -H "Authorization: Bearer SEU_TOKEN_JWT_AQUI"
```

---

### 8. Listar por Município + CNAE principal

```bash
curl -X GET "http://45.161.137.26:8430/api/cnpj/municipio/SAO%20PAULO/cnae_principal/1099699?page=1" \
  -H "Authorization: Bearer SEU_TOKEN_JWT_AQUI"
```

---

### 9. Listar por Município + CNAE secundária

```bash
curl -X GET "http://45.161.137.26:8430/api/cnpj/municipio/SAO%20PAULO/cnae_secundaria/1052000?page=1" \
  -H "Authorization: Bearer SEU_TOKEN_JWT_AQUI"
```

---

## 🔗 Rotas de Cruzamento (Relacionamentos entre CNPJs)

> **Acesso restrito a usuários ativos (plano limitado ou ilimitado)!**

---

### 10. Buscar CNPJs que compartilham o **mesmo endereço**

```bash
curl -X GET "http://45.161.137.26:8430/api/cnpj/enderecos/compartilhados?endereco=QUADRA%205%20BLOCO%20B%20TORRE%20I,%20II,%20III" \
  -H "Authorization: Bearer SEU_TOKEN_JWT_AQUI"
```

---

### 11. Buscar CNPJs que compartilham o **mesmo e-mail**

```bash
curl -X GET "http://45.161.137.26:8430/api/cnpj/emails/compartilhados?email=SECEX@BB.COM.BR" \
  -H "Authorization: Bearer SEU_TOKEN_JWT_AQUI"
```

---

### 12. Buscar CNPJs que compartilham o **mesmo telefone**

```bash
curl -X GET "http://45.161.137.26:8430/api/cnpj/telefones/compartilhados?ddd=61&telefone=34939002" \
  -H "Authorization: Bearer SEU_TOKEN_JWT_AQUI"
```

---

### 13. Listar **endereços** compartilhados por mais de um CNPJ

```bash
curl -X GET "http://45.161.137.26:8430/api/cnpj/enderecos/duplicados?minimo=2" \
  -H "Authorization: Bearer SEU_TOKEN_JWT_AQUI"
```

---

### 14. Listar **telefones** compartilhados por mais de um CNPJ

```bash
curl -X GET "http://45.161.137.26:8430/api/cnpj/telefones/duplicados?minimo=2" \
  -H "Authorization: Bearer SEU_TOKEN_JWT_AQUI"
```

---

### 15. Listar **e-mails** compartilhados por mais de um CNPJ

```bash
curl -X GET "http://45.161.137.26:8430/api/cnpj/emails/duplicados?minimo=2" \
  -H "Authorization: Bearer SEU_TOKEN_JWT_AQUI"
```

---

### 16. Buscar **todos os vínculos** (endereços, e-mails, telefones) de um CNPJ

```bash
curl -X GET "http://45.161.137.26:8430/api/cnpj/vinculos/60409075000152" \
  -H "Authorization: Bearer SEU_TOKEN_JWT_AQUI"
```

---

## 🛡️ Segurança

* **Todas as rotas exigem autenticação JWT.**
* Acesso a rotas de filtros/cruzamentos: apenas usuários ativos (limitado ou ilimitado).
* Sua conta pode ser bloqueada em caso de uso abusivo.

---

## ℹ️ Sobre

* **Base de dados:** Receita Federal + tabelas auxiliares (CNAE, Município, etc) + cruzamentos inteligentes.
* **Formato das respostas:** JSON estruturado, trazendo informações completas da empresa, sócios, contatos e relacionamentos.

---

**Dúvidas ou problemas?**
Abra um issue ou contate o suporte responsável pela API.
