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
- merchant_raw
- merchant_normalized
- description_raw
- category_id
- subcategory_id
- is_recurring
- duplicate_fingerprint

### transaction_rule
- id
- priority
- matcher_type
- matcher_value
- category_id
- enabled

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
