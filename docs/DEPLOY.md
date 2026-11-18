# Guia de deploy

Passo a passo para colocar o bot no ar usando apenas serviços gratuitos:
**Neon** (PostgreSQL), **Render** (aplicação), **Brevo** (e-mail por API HTTPS)
e **cron-job.org** (lembretes).

> Planos, limites e preços desses serviços mudam. Confira a página oficial de
> cada um antes de seguir.

## Visão geral

```
Meta (WhatsApp) ──► Render (Django + gunicorn) ──► Neon (PostgreSQL)
                         ▲            │
        cron-job.org ────┘            └──► Brevo (e-mail por API HTTPS)
   (POST a cada 10 min)
```

## Pré-requisitos

- Repositório no GitHub com a branch `main` atualizada
- Contas em Neon, Render, Brevo e cron-job.org
- Python 3.11 e o projeto rodando localmente (`python -m pytest --reuse-db -v`)

## 1. Banco de dados (Neon)

1. Crie um projeto no Neon, **separado** do banco de desenvolvimento.
2. Copie a *connection string* e guarde-a apenas no gerenciador de segredos do
   Render (passo 3). **Nunca** a coloque em arquivo versionado, issue ou chat.
3. A extensão `btree_gist` (usada pela constraint que impede horários
   sobrepostos) é criada pelas migrations. Se o seu usuário não tiver permissão
   para isso, habilite-a no SQL Editor do Neon:

   ```sql
   CREATE EXTENSION IF NOT EXISTS btree_gist;
   ```

## 2. E-mail (Brevo)

1. Crie uma conta no Brevo e gere uma chave de API.
2. Cadastre e valide o e-mail remetente.
3. Em produção o envio é feito por **API HTTPS** (via `django-anymail`), porque
   o plano gratuito do Render bloqueia portas SMTP. Gmail SMTP só é usado em
   desenvolvimento.

Limitações conhecidas: sem domínio próprio o remetente pode cair no spam, e
*bounces* não são tratados.

## 3. Aplicação (Render)

1. No Render: **New +** → **Web Service** → conecte o repositório
   `whatsapp-bot`, branch `main`.
2. Configure:

   | Campo | Valor |
   |---|---|
   | Runtime | Python 3 |
   | Build Command | `./build.sh` |
   | Start Command | `gunicorn config.wsgi:application --workers 1 --threads 4 --timeout 60 --access-logfile /dev/null` |
   | Health Check Path | `/health/` |

3. O `build.sh` instala dependências, coleta arquivos estáticos, roda as
   migrations e executa `create_owner_group` e `seed_bot_replies`.
4. Por que **1 worker e 4 threads**: o *rate limit* usa cache em memória. Com
   vários workers, cada um teria seu próprio contador.

### Variáveis de ambiente

Defina em **Environment** no Render. Nunca versione valores reais; o repositório
traz apenas o `.env.example`.

| Variável | Descrição |
|---|---|
| `DATABASE_URL` | Connection string do Neon (produção) |
| `ADMIN_URL` | Caminho secreto do Django Admin |
| `REMINDER_CRON_TOKEN` | Token do endpoint de lembretes (mínimo 32 caracteres) |
| `NUM_PROXIES` | `2` no Render (Cloudflare + balanceador) |
| `WHATSAPP_VERIFY_TOKEN` | Token escolhido por você, informado também na Meta |
| `WHATSAPP_APP_SECRET` | App Secret da Meta (valida `X-Hub-Signature-256`) |
| `WHATSAPP_ACCESS_TOKEN` | Token de acesso da WhatsApp Cloud API |
| `WHATSAPP_REMINDER_TEMPLATE` | Nome do template de lembrete (idioma `pt_BR`) |
| *(secret key, hosts permitidos, módulo de settings e chave do Brevo)* | Use os nomes exatos definidos em `config/settings/prod.py` e no `.env.example` |

Para gerar um segredo forte (por exemplo, o `REMINDER_CRON_TOKEN`):

```cmd
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## 4. Superusuário de produção

O plano gratuito do Render não oferece shell. Alternativa segura: rodar o
comando localmente apontando para o banco de produção, **no terminal em que a
variável foi definida e nunca rodando pytest nele**:

```cmd
set DATABASE_URL=<cole aqui, apenas no seu terminal>
python manage.py createsuperuser
```

Feche esse terminal em seguida. Depois acesse o admin pelo caminho definido em
`ADMIN_URL` e cadastre o negócio.

## 5. Lembretes (cron-job.org)

O Render gratuito "dorme" quando fica ocioso, então um agendador interno não é
confiável. Um cron externo aciona o endpoint:

- **URL:** `https://<seu-servico>.onrender.com/cron/send-reminders/`
- **Método:** `POST`
- **Header:** `Authorization: Bearer <REMINDER_CRON_TOKEN>`
- **Frequência:** a cada 10 minutos

Teste manualmente; deve retornar `200`. Sem o token correto, a resposta deve
ser de recusa (401/403), nunca `200`.

## 6. Conectar o WhatsApp (Meta for Developers)

1. Crie um app com o produto **WhatsApp** e use o número de teste.
2. Cadastre seu celular como destinatário de teste.
3. Crie o template de lembrete (idioma `pt_BR`) com os parâmetros:
   `{{1}}` serviço, `{{2}}` dia (dd/mm), `{{3}}` hora, `{{4}}` negócio.
4. No Render, defina `WHATSAPP_APP_SECRET`, `WHATSAPP_ACCESS_TOKEN` e
   `WHATSAPP_REMINDER_TEMPLATE`.
5. No admin, troque `PENDENTE-META` pelo `phone_number_id` real do negócio.
6. Na Meta, configure o webhook:
   - **URL:** `https://<seu-servico>.onrender.com/webhook/whatsapp/`
   - **Verify token:** o mesmo valor de `WHATSAPP_VERIFY_TOKEN`
   - Assine o campo `messages`.
7. Envie uma mensagem do seu celular e confirme a resposta do bot.

## 7. Verificação final

- [ ] `GET /health/` responde `200`
- [ ] Login no admin funciona pelo caminho secreto
- [ ] Webhook sem assinatura válida é rejeitado
- [ ] Cron responde `200` com o token e é recusado sem ele
- [ ] Agendar → e-mail de confirmação chega (confira o spam)
- [ ] Nenhum segredo no repositório (`git log -p | findstr /i "secret token"`)
- [ ] Logs sem dados pessoais (LGPD)

## Solução de problemas

| Sintoma | Causa provável |
|---|---|
| Primeira requisição lenta | Instância gratuita "acordando" |
| `403` no webhook | `WHATSAPP_APP_SECRET` incorreto ou corpo alterado antes da validação |
| Verificação do webhook falha | `WHATSAPP_VERIFY_TOKEN` diferente do informado na Meta |
| Rate limit atingindo todos | `NUM_PROXIES` incorreto (IP do proxy sendo contado) |
| E-mail não chega | Caiu no spam (sem domínio próprio) ou chave do Brevo inválida |
| Lembretes não saem | Cron pausado, token errado ou fora da janela de 24h sem template aprovado |