# Mortgage Engine

## Implementado

### Amortización estándar
Input:
- principal;
- TIN anual decimal;
- meses.

Output:
- cuota;
- pagos totales;
- intereses totales.

### Amortización extraordinaria
Input adicional:
- importe extraordinario;
- comisión total conocida.

Compara:
1. **reducir cuota** manteniendo plazo;
2. **reducir plazo** manteniendo aproximadamente la cuota original.

Devuelve para ambos:
- nueva cuota o nuevo plazo;
- intereses restantes;
- ahorro de intereses neto de la comisión indicada.

No se presupone una comisión legal: el valor debe proceder de evidencia/entrada explícita.

### Switching genérico
El motor de optimización calcula:
`ahorro bruto - coste cambio - penalizaciones - beneficios perdidos - coste recurrente adicional - impacto fiscal`

Si la penalización es desconocida, el resultado es `needs_more_data`.

## No implementado como automatismo completo
- FEIN/FIAE estructurada en todos sus campos;
- curvas variables/mixtas y revisiones de índice;
- novación/subrogación;
- costes legales por jurisdicción/fecha;
- ofertas bancarias comerciales automáticas.

Estos elementos deben añadirse como facts versionados y nunca como constantes “universales”.


## Laboratorio conectado a la hipoteca real

El Laboratorio dispone de un perfil hipotecario persistente con:
- entidad;
- capital pendiente actual;
- tipo fijo/variable/mixto;
- TIN actual;
- cuota mensual real;
- meses restantes;
- comisión total conocida de amortización anticipada.

Los cálculos de escenario base, amortización extraordinaria y senda hipotética reciben un `mortgage_id` y leen estos valores de la base local. La interfaz no precarga capitales, tipos o plazos de ejemplo.

Cada alta/actualización de hipoteca genera un snapshot temporal.

### Amortización extraordinaria

El usuario solo introduce el importe hipotético a amortizar. Capital, TIN, plazo y comisión proceden de la hipoteca guardada. Si la comisión es desconocida, el cálculo se bloquea en vez de asumir 0.

### Senda de tipos

El capital, plazo y TIN inicial son los reales guardados. Los cambios futuros de tipo son assumptions explícitos del usuario y nunca se presentan como predicción.


## Vinculación documental y selección de hipoteca

Una escritura, FEIN o anexo hipotecario no modifica ninguna hipoteca mientras permanezca sin vínculo explícito.

Desde **Documentos y evidencia** el usuario puede:
- vincular el documento a una hipoteca existente;
- crear el perfil hipotecario inicial desde el propio documento y enlazarlo en el mismo flujo;
- rellenar el alta con hechos materiales ya confirmados en ese documento.

Una vez enlazado, la proyección documental actualiza únicamente campos compatibles y confirmados. Una oferta alternativa puede permanecer sin vínculo para compararla sin contaminar la situación vigente.

El selector de **Hipoteca utilizada en las simulaciones** es la fuente de `mortgage_id` para:
- escenario base;
- amortización extraordinaria;
- senda hipotética de tipos;
- comparación de mercado.

La investigación de mercado recibe el mismo `mortgage_id`; nunca debe comparar silenciosamente contra “la última hipoteca modificada” si el usuario ha seleccionado otra.

## Conclusión de mercado hipotecario

Las referencias públicas se ordenan por impacto económico calculable, no solo por menor TIN.

Para poder señalar una referencia concreta:
1. debe existir ahorro mensual frente al escenario comparable;
2. debe existir ahorro de intereses restante positivo después de la penalización de salida conocida;
3. el break-even calculable debe ocurrir antes del vencimiento restante;
4. los costes contractuales materiales exigidos por `switching_readiness` deben estar confirmados.

Si falta una penalización, vinculación o evidencia material, el estado es `needs_more_data` y la interfaz indica qué dato confirmar. Si existe una referencia favorable, Financito indica qué entidad merece solicitar como FEIN/oferta personalizada y recomienda contrastarla primero con la entidad actual; la decisión final solo se calcula cuando se incorporan los costes y condiciones personalizados.


## Regla de superioridad de una referencia de mercado

Una oferta pública no se considera mejor por el TIN de forma aislada. El comparador mantiene capital y plazo restantes, calcula la cuota candidata y la contrasta con la cuota real guardada. Con una penalización de salida confirmada:

\`ahorro_mensual_real = cuota_actual_guardada - cuota_candidata\`

\`break_even_meses = penalizacion_salida / ahorro_mensual_real\`

La referencia solo entra en \`better_offers\` cuando el ahorro mensual es positivo, el ahorro de intereses conocido supera la penalización y el punto de equilibrio es anterior al vencimiento. Si la referencia requiere un seguro vinculado cuyo coste no está disponible, la comparación se marca incompleta y no se afirma que sea mejor. Tasación, costes de una FEIN u otros importes no confirmados nunca se presuponen como cero.


## TAE estimada sobre el saldo restante

Financito conserva la TAE contractual como evidencia original. Para describir el coste actual puede calcular una **TAE estimada restante** resolviendo la tasa interna mensual que iguala el capital pendiente con los flujos futuros conocidos:

\`capital_pendiente = Σ[(cuota_calculada + costes_vinculados_mensuales_conocidos) / (1+r_m)^t]\`

y anualiza:

\`TAE_estimada = (1 + r_m)^12 - 1\`

Esta tasa no es una nueva TAE contractual: excluye costes hundidos ya pagados y solo incorpora costes futuros actualmente estructurados.

## Revisión automática de hipoteca variable

Una revisión automática requiere evidencia confirmada de:
- índice de referencia;
- diferencial;
- periodicidad de revisión;
- fecha de la próxima revisión;
- desfase exacto entre la fecha de revisión y el mes/publicación del índice (\`reference_index_lag_months\`).

Para Euríbor 12 meses se usa la serie mensual oficial del BCE \`FM.M.U2.EUR.RT.MM.EURIBOR1YD_.HSTA\`. El motor calcula:

\`TIN_estimado = indice_oficial + diferencial_confirmado\`

y vuelve a amortizar el capital/plazo restantes para obtener cuota e intereses estimados. El resultado se etiqueta como estimación y exige confirmación; no sobrescribe automáticamente el TIN/cuota guardados.
