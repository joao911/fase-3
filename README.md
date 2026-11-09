# FarmTech Solutions — Fase 3

A fase 2 decide se a bomba do tomateiro liga. A fase 3 guarda essa decisão. O grupo exporta as leituras, limpa o ruído com NumPy e Pandas, calcula indicadores de manejo, desenha o comportamento dos sensores e persiste o histórico no Oracle.

A cultura é o tomate (*Solanum lycopersicum*), na frutificação. Os sensores seguem o circuito da fase 2:

| Sensor | O que mede | No CSV e no banco |
| --- | --- | --- |
| S1 | Umidade do solo | `umidade` |
| S2 | pH do solo | `ph` |
| S3 | Fósforo e potássio | `fosforo` e `potassio` |

O nitrogênio entra junto porque a regra da bomba também depende dele. A chuva entra porque, a partir de 60%, o relé desliga.

## Como executar

A pasta `fase 2` precisa estar ao lado de `fase 3`. A geração usa a função `decidir` de `fase 2/farmtech`.

```bash
cd "fase 3"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
python -m unittest testes/test_pipeline.py -v
```

`python main.py` regrava o CSV bruto, o CSV tratado, `dados/indicadores.json` e os quatro gráficos. Para carregar o banco e executar as consultas:

```bash
cp .env.example .env
python main.py --oracle
```

Preencha `ORACLE_USER` e `ORACLE_PASSWORD` no `.env`. Esse arquivo fica de fora do envio, assim como a pasta `.venv`.

Dependências, em `requirements.txt`: NumPy, Pandas, Matplotlib, Seaborn e `oracledb`.

## Estrutura

```text
fase 3/
  main.py                         pipeline completo
  farmtech_dados/
    gerar_leituras.py             histórico horário e defeitos de sensor
    tratar.py                     tipos, faixa física e média móvel
    indicadores.py                água, acionamentos e correlação
    graficos.py                   quatro figuras
    oracle_carga.py               tabelas, carga e consultas
    parametros.py                 datas, vazão e limiares
  sql/schema.sql                  criação das tabelas
  sql/consultas.sql               uma consulta por informação de gestão
  dados/                          CSV, indicadores e resultado das consultas
  graficos/                       figuras da análise
  testes/test_pipeline.py         regra da fase 2, limpeza e arquivos
fase 2/dados/cultura.txt          cultura e limiares das fases 1 e 2
fase 2/dados/insumos.json         vazão do setor e doses de N, P e K
```

## Parte 1 — do Monitor Serial ao gráfico

### Premissas da série

Não há captura do Monitor Serial do Wokwi neste repositório. O enunciado permite completar o volume em Python, desde que cada linha fique marcada e as premissas fiquem escritas. Por isso toda linha nasce com `origem = simulada`.

O relógio é o da fase 2: cada ciclo vale uma hora. O arquivo cobre de 2026-06-01 00:00 a 2026-08-31 23:00, 2208 horas, três meses. A semente do ruído é 42, então a série se repete igual.

A bomba chama a mesma função `decidir` da fase 2:

- liga abaixo de 70% de umidade se o pH está entre 6,0 e 6,5, se N, P e K estão adequados e se não há chuva;
- entre 70% e 80% mantém o estado anterior;
- desliga a partir de 80%, ou quando a chuva chega a 60%.

A umidade do modelo sobe cerca de 2 pontos percentuais por hora com a bomba ligada, cai cerca de 0,7 ponto com ela desligada e sobe cerca de 3,8 pontos nas horas de chuva. O pH caminha para o valor sugerido pelo NPK da fase 2. O CSV grava a leitura já com ruído, e é essa leitura que entra na decisão. O ruído é normal, com desvio 0,8 na umidade e 0,04 no pH.

Eventos colocados para o histórico não ficar constante:

- dias 5 e 6: falta nitrogênio;
- dias 20 a 22: falta potássio;
- dias 45 e 46: falta fósforo;
- dias 70 a 72: o pH vai para cerca de 7,1 e a bomba fica bloqueada;
- dias 8, 19, 33, 41, 58, 66, 80 e 88, das 15h às 20h: chuva.

Dezesseis linhas foram estragadas de propósito, com célula vazia, texto ou número fora da faixa do sensor, para o tratamento ter o que remover.

Colunas de `dados/leituras_brutas.csv`: `data_hora`, `umidade`, `ph`, `fosforo`, `potassio`, `nitrogenio`, `chuva`, `bomba`, `origem`. Fósforo, potássio, nitrogênio, chuva e bomba valem 1 ou 0.

### Tratamento

`tratar.py` lê o CSV com Pandas, converte a data e os números e descarta o que não dá para usar: umidade fora de 0 a 100, pH fora de 0 a 14, flag diferente de 0 ou 1, texto no lugar de número e célula vazia. Das 2208 linhas, 16 saem. Ficam 2192.

A média móvel é calculada com NumPy, numa janela de 6 leituras válidas, sobre umidade e pH. O resultado vai para `umidade_suavizada` e `ph_suavizado` em `dados/leituras_tratadas.csv`. A variância da umidade suavizada fica menor que a da leitura crua.

### Indicadores

A vazão do setor é 500 L/h, numa área de 500 m². Cada linha com a bomba ligada representa uma hora, então o volume é horas ligadas vezes 500. No período, isso corresponde a cerca de 5,6 mm por dia.

No histórico tratado a bomba ficou ligada 515 horas, em 83 acionamentos. A água estimada é 257.500 L.

| Mês | Água | Umidade suavizada | pH suavizado |
| --- | --- | --- | --- |
| 2026-06 | 87.000 L | 41,5% a 92,1% | 6,06 a 6,72 |
| 2026-07 | 86.500 L | 40,3% a 92,7% | 6,05 a 6,42 |
| 2026-08 | 84.000 L | 34,1% a 92,5% | 6,06 a 7,13 |

O arquivo `dados/indicadores.json` traz o mesmo resumo por dia: horas de bomba, número de acionamentos, litros, média e extremos de umidade e de pH.

### Gráficos

Os arquivos estão em `graficos/`.

- `evolucao_umidade_ph.png` mostra a média diária da umidade e do pH nos três meses. Os vales de umidade coincidem com a falta de nutriente ou com o pH alto.
- `umidade_e_bomba.png` mostra, de 18/06 a 02/07, a leitura crua, a média móvel e as horas em que a bomba ficou ligada. As linhas de 70% e 80% são a histerese da fase 2. O vale sem irrigação é a falta de potássio.
- `distribuicao_sensores.png` traz o histograma da umidade, o histograma do pH e as horas com nutriente adequado ou deficiente.
- `correlacao.png` é o mapa de calor da matriz de correlação entre umidade, pH, nutrientes, chuva e bomba.

A umidade é a variável com maior relação linear com a bomba, correlação −0,13. O pH vem em seguida, também −0,13. Potássio (+0,10), fósforo (+0,08) e nitrogênio (+0,08) sobem juntos com a decisão de irrigar, porque a bomba só liga quando eles estão presentes. A chuva fica em −0,08, porque o relé desliga.

A correlação linear é baixa porque a regra não é uma reta. Entre 70% e 80% a bomba continua ligada enquanto a umidade sobe, então a hora irrigada não é a hora mais seca. A regra aparece no gráfico da bomba. No banco, a umidade média do S1 foi 71,52% com a bomba ligada e 74,49% com ela desligada.

## Parte 2 — Oracle e primeira persistência

### Informações que a fazenda precisa responder

Esta lista orienta as tabelas desta fase e a modelagem da fase 4. Cada linha tem uma consulta em `sql/consultas.sql`. O resultado executado está em `dados/resultado_consultas.txt`.

| Informação | Dados necessários |
| --- | --- |
| Quantidade total de água aplicada em cada mês | Data e hora de cada hora com a bomba ligada e a vazão do setor |
| Variação do pH ao longo do tempo | Data e hora das leituras do sensor S2 e o valor de pH |
| Dias com maior tempo de bomba ligada | Início, fim e duração de cada acionamento |
| Cultura com maior consumo de água e de insumos | Cultura, volume aplicado e doses de N, P e K das fases 1 e 2 |
| Horas com deficiência de fósforo ou potássio | Data e hora e o estado do sensor S3 |
| Umidade do solo com a irrigação ligada e desligada | Leituras do sensor S1 e o estado da bomba |

### Ambiente e conexão

O banco usado é o Oracle acadêmico da FIAP, já provisionado na nuvem. A conexão sai de `farmtech_dados/oracle_carga.py` pelo driver `oracledb` em modo thin, sem Oracle Instant Client.

1. Use os dados da disciplina: host `oracle.fiap.com.br`, porta `1521`, SID `ORCL`.
2. Copie `.env.example` para `.env` e preencha usuário e senha.
3. Rode `python main.py --oracle`.
4. No SQL Developer, crie uma conexão com o mesmo host, a mesma porta, o SID `ORCL` e o usuário da FIAP. As consultas de `sql/consultas.sql` podem ser coladas nessa sessão.

Se a conta da FIAP não estiver disponível, a alternativa local é o Oracle Database Free em container:

```bash
docker run -d --name oracle-free -p 1521:1521 \
  -e ORACLE_PWD=uma_senha \
  container-registry.oracle.com/database/free:latest
```

Nesse caso o `.env` aponta o host para `localhost`. A imagem publica o serviço `FREEPDB1`, e o programa desta entrega conecta por SID. O caminho testado foi a nuvem da FIAP.

### Tabelas

O desenho está em `sql/schema.sql`. Cada tabela tem chave primária numérica. Os tipos acompanham o conteúdo: `TIMESTAMP` para data e hora, `NUMBER` para medidas e doses, `VARCHAR2` para nomes e textos.

| Tabela | O que guarda | Origem |
| --- | --- | --- |
| `ft_culturas` | Nome, fase, faixa de pH e umidade de ligar e desligar | `fase 2/dados/cultura.txt` |
| `ft_manejo` | Vazão de 500 L/h e área de 500 m² | `fase 2/dados/insumos.json` |
| `ft_insumos` | Doses de nitrogênio, fósforo e potássio em kg/ha | o mesmo JSON |
| `ft_leituras` | Uma hora de S1, S2, S3, chuva, bomba e médias móveis | CSV tratado |
| `ft_historico_bomba` | Cada período contínuo de bomba ligada, com horas e litros | CSV tratado |

`ft_leituras.data_hora` e `ft_historico_bomba.inicio` são únicos. Leituras e acionamentos apontam para a cultura.

As doses gravadas são as da fase 2, na faixa usada a partir da Embrapa: nitrogênio de 80 a 120 kg/ha, fósforo (P₂O₅) de 300 a 450 kg/ha e potássio (K₂O) de 50 a 100 kg/ha.

### Carga

`oracle_carga.py` lê o CSV tratado, o texto da cultura e o JSON de insumos. Na primeira execução contra um esquema antigo, recria as tabelas. Nas seguintes, apaga as linhas desta safra e insere de novo. Uma segunda execução não duplica: ficam 1 cultura, 1 manejo, 3 insumos, 2192 leituras e 83 acionamentos.

### Respostas

- Água no tomateiro: junho 87.000 L, julho 86.500 L e agosto 84.000 L.
- A maior variação semanal de pH foi a semana de 10/08, de 6,02 a 7,18. Nesse intervalo o solo do modelo ficou alcalino e a irrigação parou.
- Os dias com a bomba ligada por mais tempo foram 18/07 e 13/08, com 23 horas e 11.500 L cada.
- A cultura cadastrada é o tomate, com 257.500 L no período. O insumo de maior dose recomendada é o fósforo.
- O sensor S3 ficou sem potássio por 72 horas em junho e sem fósforo por 48 horas em julho.
- A umidade média do S1 foi 71,52% com a bomba ligada e 74,49% com ela desligada.
