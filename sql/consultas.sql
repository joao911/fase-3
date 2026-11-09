-- 1. Quantidade total de água aplicada em cada mês
SELECT TO_CHAR(TRUNC(l.data_hora, 'MM'), 'YYYY-MM') AS mes,
       c.nome AS cultura,
       SUM(l.bomba) AS horas_bomba,
       ROUND(SUM(l.bomba) * MAX(m.vazao_l_h), 1) AS litros
FROM ft_leituras l
JOIN ft_culturas c ON c.id = l.cultura_id
JOIN ft_manejo m ON m.cultura_id = c.id
GROUP BY TRUNC(l.data_hora, 'MM'), c.nome
ORDER BY TRUNC(l.data_hora, 'MM');

-- 2. Variação do pH do sensor S2 por semana
SELECT TO_CHAR(TRUNC(data_hora, 'IW'), 'YYYY-MM-DD') AS semana,
       ROUND(MIN(ph), 2) AS ph_minimo,
       ROUND(AVG(ph), 2) AS ph_medio,
       ROUND(MAX(ph), 2) AS ph_maximo,
       ROUND(MAX(ph) - MIN(ph), 2) AS variacao
FROM ft_leituras
GROUP BY TRUNC(data_hora, 'IW')
ORDER BY TRUNC(data_hora, 'IW');

-- 3. Dias com maior tempo de bomba ligada
SELECT TO_CHAR(TRUNC(inicio), 'YYYY-MM-DD') AS dia,
       SUM(horas) AS horas_bomba,
       ROUND(SUM(volume_litros), 1) AS litros
FROM ft_historico_bomba
GROUP BY TRUNC(inicio)
ORDER BY horas_bomba DESC, dia
FETCH FIRST 5 ROWS ONLY;

-- 4. Culturas e consumo de água e de insumos
SELECT c.nome AS cultura,
       ROUND(SUM(h.volume_litros), 1) AS agua_litros,
       i.nome AS insumo,
       i.dose_min_kg_ha,
       i.dose_max_kg_ha
FROM ft_culturas c
JOIN ft_historico_bomba h ON h.cultura_id = c.id
JOIN ft_insumos i ON i.cultura_id = c.id
GROUP BY c.nome, i.nome, i.dose_min_kg_ha, i.dose_max_kg_ha
ORDER BY agua_litros DESC, i.dose_max_kg_ha DESC;

-- 5. Horas em que o sensor S3 registrou deficiência de fósforo ou potássio
SELECT TO_CHAR(TRUNC(data_hora, 'MM'), 'YYYY-MM') AS mes,
       SUM(CASE WHEN fosforo = 0 THEN 1 ELSE 0 END) AS horas_sem_fosforo,
       SUM(CASE WHEN potassio = 0 THEN 1 ELSE 0 END) AS horas_sem_potassio
FROM ft_leituras
GROUP BY TRUNC(data_hora, 'MM')
ORDER BY TRUNC(data_hora, 'MM');

-- 6. Umidade do sensor S1 com a bomba ligada e desligada
SELECT CASE WHEN bomba = 1 THEN 'ligada' ELSE 'desligada' END AS bomba,
       ROUND(AVG(umidade), 2) AS umidade_media_s1,
       COUNT(*) AS leituras
FROM ft_leituras
GROUP BY bomba
ORDER BY bomba;
