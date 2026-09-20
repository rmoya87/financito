# Modelo de datos

Este documento define entidades lógicas; el esquema físico se versionará con migraciones.

## Identidad y auditoría

Toda entidad principal:
- id UUID;
- created_at;
- updated_at.

Datos externos además:
- source;
- source_id;
- fetched_at;
- source_updated_at.

## Perfil

### user_profile
- id
- display_name
- base_currency
- locale
- timezone
- created_at

### financial_profile
- emergency_fund_months
- target_cash_buffer
- risk_tolerance
- investment_horizon
- max_crypto_allocation
- max_single_stock_allocation
- max_sector_allocation

## Bancos

### institution
- id
- name
- provider
- country

### account
- id
- institution_id
- external_id
- name
- type
- currency
- iban_masked
- current_balance
- available_balance
- sync_status
- consent_expires_at

### transaction
- id
- account_id
- external_id
- booking_date
- value_date
- amount
- currency
- original_amount
- original_currency
- base_amount
- base_currency
- fx_rate
- fx_rate_date
- merchant_raw
- merchant_normalized
- merchant_group_id
- description_raw
- description_normalized
- category_id
- subcategory_id
- necessity_class
- variability_class
- is_recurring
- recurring_series_id
- is_internal_transfer
- matched_transfer_id
- refund_of_transaction_id
- duplicate_fingerprint
- categorization_method
- categorization_confidence
- categorization_version
- user_verified
- ownership_type
- ownership_percentage

### category
- id
- parent_id
- name
- system_key
- is_system
- enabled

### merchant_group
- id
- canonical_name
- category_hint
- user_verified

### merchant_alias
- id
- merchant_group_id
- normalized_pattern
- matcher_type
- confidence
- source

### transaction_rule
- id
- priority
- matcher_type
- matcher_value
- category_id
- subcategory_id
- necessity_class
- variability_class
- enabled

### transaction_split
- id
- transaction_id
- amount
- category_id
- subcategory_id
- note

Constraint: la suma exacta de splits debe coincidir con el importe del movimiento.

### categorization_audit
- id
- transaction_id
- previous_category_id
- new_category_id
- method
- confidence
- algorithm_version
- changed_by
- changed_at

## Recurrentes

### recurring_series
- id
- merchant_normalized
- cadence
- expected_amount
- amount_tolerance
- next_expected_date
- confidence
- status

## Documentos

### document
- id
- file_path
- file_name
- mime_type
- sha256
- language
- document_type
- status
- page_count
- extracted_text_hash
- indexed_at
- excluded_from_ai

### document_page
- id
- document_id
- page_number
- text
- ocr_used

### document_chunk
- id
- document_id
- page_start
- page_end
- heading
- section
- text
- token_count
- chunk_index
- embedding_model
- embedding_version

### extracted_fact
- id
- document_id
- fact_type
- key
- value_json
- confidence
- source_page
- source_chunk_id
- user_verified

## Contratos

### contract
- id
- provider_name
- type
- start_date
- renewal_date
- cancellation_notice_days
- permanence_end_date
- early_exit_penalty
- annual_cost
- currency

### benefit
- id
- contract_id nullable
- name
- benefit_type
- theoretical_value
- realized_value
- user_adjusted_value
- period

### linked_product
- id
- parent_product_type
- parent_product_id
- linked_product_type
- linked_product_id
- discount_value
- discount_unit
- conditions

## Seguros

### insurance_policy
- id
- contract_id
- policy_number
- insurance_type
- annual_premium
- deductible
- coverage_json
- insured_object_json
- cancellation_terms_json

## Hipoteca

### mortgage
- id
- contract_id
- lender
- original_principal
- remaining_principal
- currency
- interest_type
- nominal_rate
- apr
- reference_index
- spread
- monthly_payment
- maturity_date
- next_revision_date
- early_repayment_fee
- subrogation_fee
- novation_fee

### mortgage_link_requirement
- id
- mortgage_id
- requirement_type
- description
- rate_discount
- annual_cost

## Patrimonio

### asset
- id
- asset_type
- name
- currency
- current_value
- valuation_date
- valuation_source

### liability
- id
- liability_type
- name
- outstanding_amount
- currency

## Inversión

### security
- id
- asset_class
- symbol
- isin
- name
- currency
- exchange
- sector
- industry

### portfolio
- id
- name
- base_currency

### position
- id
- portfolio_id
- security_id
- quantity
- average_cost
- current_price
- market_value
- unrealized_pnl

### trade
- id
- portfolio_id
- security_id
- side
- quantity
- price
- fees
- executed_at

## Mercado

### market_price
- security_id
- timestamp
- open
- high
- low
- close
- volume
- provider

### fundamental_snapshot
- security_id
- period
- revenue
- ebitda
- ebit
- net_income
- eps
- fcf
- debt
- cash
- roe
- roic
- margins_json
- ratios_json

## Cripto

Puede reutilizar security/position, pero las métricas específicas viven en crypto_snapshot:
- market_cap
- volume
- circulating_supply
- max_supply
- dominance
- volatility
- drawdown
- funding_rate
- open_interest
- metrics_json

## Noticias

### news_item
- id
- canonical_url
- source
- headline
- published_at
- event_date
- summary
- sentiment
- impact
- reliability

### news_asset_link
- news_item_id
- security_id
- relevance

## Optimización

### optimization_opportunity
- id
- category
- current_product_ref
- alternative_ref
- gross_annual_saving
- switching_costs
- penalties
- lost_benefits
- additional_recurring_costs
- tax_impact
- net_annual_benefit
- break_even_months
- confidence
- effort
- urgency
- status
- calculated_at

### recommendation_snapshot
- id
- recommendation_type
- subject_ref
- inputs_json
- outputs_json
- sources_json
- confidence
- created_at

### decision
- id
- recommendation_snapshot_id
- decision
- reason
- decided_at

## Índices clave

- transaction(account_id, booking_date)
- transaction(merchant_normalized)
- document(sha256) UNIQUE
- document_chunk(document_id, chunk_index)
- FTS sobre texto documental
- índice vectorial sobre embeddings
- news_item(canonical_url) UNIQUE
- market_price(security_id, timestamp)
- optimization_opportunity(status, urgency)


## Casos de decisión

### decision_case
- id
- decision_type
- question
- current_state_json
- assumptions_json
- constraints_json
- calculation_version
- status
- created_at

### decision_alternative
- id
- decision_case_id
- name
- one_off_cost
- monthly_cost
- annual_cost
- expected_benefit
- net_benefit
- liquidity_impact
- risk_level
- effort
- reversibility
- break_even_months
- horizon_results_json
- pros_json
- cons_json
- uncertainties_json

### decision_source
- id
- decision_case_id
- source_type
- source_ref
- source_timestamp

## Insights

### insight
- id
- insight_type
- subject_type
- subject_id
- period_start
- period_end
- title
- description
- calculation_json
- confidence
- severity
- generated_at
- dismissed_at

### anomaly
- id
- transaction_id
- anomaly_type
- baseline_json
- observed_json
- explanation
- confidence
- status

## Presupuestos

### budget
- id
- category_id
- subcategory_id
- period_type
- amount
- currency
- rollover
- alert_threshold

## Objetivos

### financial_goal
- id
- goal_type
- name
- target_amount
- current_amount
- target_date
- priority
- planned_monthly_contribution
- status

## Auditoría

### audit_event
- id
- event_type
- entity_type
- entity_id
- metadata_json
- created_at

No almacenar secretos ni payloads sensibles completos.


## Evidencia contractual

### contract_fact
- id
- contract_id
- fact_type
- value_json
- unit
- confidence
- status
- effective_from
- effective_to
- source_document_id
- source_page
- source_section
- source_chunk_id
- extraction_method
- user_verified
- supersedes_fact_id

status:
- confirmed
- inferred
- not_found
- ambiguous
- conflicting
- superseded

### contract_formula
- id
- contract_fact_id
- formula_type
- base_type
- percentage
- fixed_amount
- floor_amount
- cap_amount
- applicability_start
- applicability_end
- parameters_json

### calculation_trace
- id
- calculation_type
- engine_version
- input_name
- input_value_json
- input_source_type
- input_source_ref
- formula
- result_json
- created_at

Los traces materiales deben permitir reconstruir el cálculo y abrir la evidencia de origen.
