"""Add canonical identity and business-object tables.

Revision ID: 20260106000100
Revises: 20250102000001
Create Date: 2026-01-06 00:01:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260106000100"
down_revision = "20250102000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Agents
    op.create_table(
        "agents",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("external_agent_id", sa.String(), nullable=False, unique=True),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # 2) People & organizations
    op.create_table(
        "people",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("given_name", sa.String(), nullable=True),
        sa.Column("family_name", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "organizations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "person_organizations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("person_id", sa.BigInteger(), sa.ForeignKey("people.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "organization_id",
            sa.BigInteger(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint(
            "person_id",
            "organization_id",
            "role",
            name="uq_person_organizations_person_org_role",
        ),
    )

    # 3) Identifiers
    op.create_table(
        "identifiers",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("identifier_type", sa.String(), nullable=False),
        sa.Column("identifier_value", sa.Text(), nullable=False),
        sa.Column("normalized_value", sa.Text(), nullable=False),
        sa.Column("person_id", sa.BigInteger(), sa.ForeignKey("people.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "organization_id",
            sa.BigInteger(),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint(
            "identifier_type",
            "normalized_value",
            name="uq_identifiers_type_normalized",
        ),
    )
    op.create_index("idx_identifiers_person_id", "identifiers", ["person_id"])
    op.create_index("idx_identifiers_organization_id", "identifiers", ["organization_id"])

    # 4) Addresses & entity_addresses
    op.create_table(
        "addresses",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("line1", sa.String(), nullable=False),
        sa.Column("line2", sa.String(), nullable=True),
        sa.Column("city", sa.String(), nullable=True),
        sa.Column("state", sa.String(), nullable=True),
        sa.Column("postal_code", sa.String(), nullable=True),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "entity_addresses",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "address_id",
            sa.BigInteger(),
            sa.ForeignKey("addresses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("person_id", sa.BigInteger(), sa.ForeignKey("people.id", ondelete="CASCADE"), nullable=True),
        sa.Column(
            "organization_id",
            sa.BigInteger(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("address_type", sa.String(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "(person_id IS NOT NULL AND organization_id IS NULL) "
            "OR (person_id IS NULL AND organization_id IS NOT NULL)",
            name="chk_entity_addresses_one_owner",
        ),
    )
    op.create_index("idx_entity_addresses_person_id", "entity_addresses", ["person_id"])
    op.create_index("idx_entity_addresses_organization_id", "entity_addresses", ["organization_id"])

    # 5) Extractions
    op.create_table(
        "extractions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("call_id", sa.BigInteger(), sa.ForeignKey("calls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("extractor_name", sa.String(), nullable=False),
        sa.Column("extractor_version", sa.String(), nullable=True),
        sa.Column("run_type", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default=sa.text("'succeeded'")),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(
        "idx_extractions_call_created",
        "extractions",
        ["call_id", sa.text("created_at DESC")],
    )

    # 6) Business objects: products, tasks, offers, call_product_mentions
    op.create_table(
        "products",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("sku", sa.String(), nullable=True, unique=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("product_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "tasks",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("call_id", sa.BigInteger(), sa.ForeignKey("calls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("extraction_id", sa.BigInteger(), sa.ForeignKey("extractions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("fact_id", sa.BigInteger(), nullable=True),  # FK added after extracted_facts creation
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default=sa.text("'open'")),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("owner_agent_id", sa.BigInteger(), sa.ForeignKey("agents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("person_id", sa.BigInteger(), sa.ForeignKey("people.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "organization_id",
            sa.BigInteger(),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("stable_key", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_tasks_call_id", "tasks", ["call_id"])
    op.create_index("idx_tasks_owner_agent", "tasks", ["owner_agent_id"])
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_tasks_call_stable_key ON tasks(call_id, stable_key) WHERE stable_key IS NOT NULL"
    )

    op.create_table(
        "offers",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("call_id", sa.BigInteger(), sa.ForeignKey("calls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.BigInteger(), sa.ForeignKey("products.id", ondelete="SET NULL"), nullable=True),
        sa.Column("extraction_id", sa.BigInteger(), sa.ForeignKey("extractions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("fact_id", sa.BigInteger(), nullable=True),  # FK added after extracted_facts creation
        sa.Column("person_id", sa.BigInteger(), sa.ForeignKey("people.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "organization_id",
            sa.BigInteger(),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default=sa.text("'promised'")),
        sa.Column("discount_amount", sa.Double(), nullable=True),
        sa.Column("discount_percent", sa.Double(), nullable=True),
        sa.Column("price_amount", sa.Double(), nullable=True),
        sa.Column("price_currency", sa.String(length=3), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("conditions", sa.Text(), nullable=True),
        sa.Column("stable_key", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_offers_call_id", "offers", ["call_id"])
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_offers_call_stable_key ON offers(call_id, stable_key) WHERE stable_key IS NOT NULL"
    )

    op.create_table(
        "call_product_mentions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("call_id", sa.BigInteger(), sa.ForeignKey("calls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.BigInteger(), sa.ForeignKey("products.id", ondelete="SET NULL"), nullable=True),
        sa.Column("extraction_id", sa.BigInteger(), sa.ForeignKey("extractions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("fact_id", sa.BigInteger(), nullable=True),  # FK added after extracted_facts creation
        sa.Column("person_id", sa.BigInteger(), sa.ForeignKey("people.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "organization_id",
            sa.BigInteger(),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("mentioned_name", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Double(), nullable=True),
        sa.Column("quantity_unit", sa.String(), nullable=True),
        sa.Column("price_amount", sa.Double(), nullable=True),
        sa.Column("price_currency", sa.String(length=3), nullable=True),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("start_sec", sa.Double(), nullable=True),
        sa.Column("end_sec", sa.Double(), nullable=True),
        sa.Column("stable_key", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_call_product_mentions_call_id", "call_product_mentions", ["call_id"])
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_call_product_mentions_call_stable_key ON call_product_mentions(call_id, stable_key) WHERE stable_key IS NOT NULL"
    )

    # 7) Extracted facts (after business tables so FKs can reference them)
    op.create_table(
        "extracted_facts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("extraction_id", sa.BigInteger(), sa.ForeignKey("extractions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("call_id", sa.BigInteger(), sa.ForeignKey("calls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fact_type", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default=sa.text("'proposed'")),
        sa.Column("confidence", sa.Double(), nullable=False),
        sa.Column("turn_id", sa.BigInteger(), sa.ForeignKey("dialogue_turns.id", ondelete="SET NULL"), nullable=True),
        sa.Column("start_sec", sa.Double(), nullable=True),
        sa.Column("end_sec", sa.Double(), nullable=True),
        sa.Column("raw_span_text", sa.Text(), nullable=True),
        sa.Column("person_id", sa.BigInteger(), sa.ForeignKey("people.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "organization_id",
            sa.BigInteger(),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("agent_id", sa.BigInteger(), sa.ForeignKey("agents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("task_id", sa.BigInteger(), sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("product_id", sa.BigInteger(), sa.ForeignKey("products.id", ondelete="SET NULL"), nullable=True),
        sa.Column("offer_id", sa.BigInteger(), sa.ForeignKey("offers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("stable_key", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_extracted_facts_call_id", "extracted_facts", ["call_id"])
    op.create_index("idx_extracted_facts_extraction_id", "extracted_facts", ["extraction_id"])
    op.create_index(
        "idx_extracted_facts_fact_type",
        "extracted_facts",
        ["call_id", "fact_type"],
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_extracted_facts_call_type_stable ON extracted_facts(call_id, fact_type, stable_key) WHERE stable_key IS NOT NULL"
    )

    # 8) Link tasks/offers/call_product_mentions.fact_id back to extracted_facts
    op.create_foreign_key(
        "fk_tasks_fact_id",
        "tasks",
        "extracted_facts",
        ["fact_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_offers_fact_id",
        "offers",
        "extracted_facts",
        ["fact_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_call_product_mentions_fact_id",
        "call_product_mentions",
        "extracted_facts",
        ["fact_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 9) Extend calls with nullable FKs and snapshot fields - only add if they don't exist
    # Check if column exists before adding
    conn = op.get_bind()
    
    # Check if columns exist before adding them
    columns_to_check = [
        "entities", "intent", "resolution", "confidence_score", 
        "agent_fk", "person_id", "organization_id"
    ]
    
    existing_columns = []
    for col_name in columns_to_check:
        result = conn.execute(
            sa.text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'calls' AND column_name = :col_name
            """),
            {"col_name": col_name}
        )
        if result.fetchone():
            existing_columns.append(col_name)
    
    # Add columns that don't exist
    if "entities" not in existing_columns:
        op.add_column("calls", sa.Column("entities", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    if "intent" not in existing_columns:
        op.add_column("calls", sa.Column("intent", sa.String(), nullable=True))
    if "resolution" not in existing_columns:
        op.add_column("calls", sa.Column("resolution", sa.String(), nullable=True))
    if "confidence_score" not in existing_columns:
        op.add_column("calls", sa.Column("confidence_score", sa.Double(), nullable=True))
    if "agent_fk" not in existing_columns:
        op.add_column("calls", sa.Column("agent_fk", sa.BigInteger(), nullable=True))
    if "person_id" not in existing_columns:
        op.add_column("calls", sa.Column("person_id", sa.BigInteger(), nullable=True))
    if "organization_id" not in existing_columns:
        op.add_column("calls", sa.Column("organization_id", sa.BigInteger(), nullable=True))

    op.create_foreign_key(
        "fk_calls_agent_fk",
        "calls",
        "agents",
        ["agent_fk"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_calls_person_id",
        "calls",
        "people",
        ["person_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_calls_organization_id",
        "calls",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_index("idx_calls_agent_fk", "calls", ["agent_fk"])
    op.create_index("idx_calls_person_id", "calls", ["person_id"])
    op.create_index("idx_calls_organization_id", "calls", ["organization_id"])
    op.create_index(
        "idx_calls_status_created",
        "calls",
        ["status", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    # Drop new FKs and columns from calls
    op.drop_index("idx_calls_status_created", table_name="calls")
    op.drop_index("idx_calls_organization_id", table_name="calls")
    op.drop_index("idx_calls_person_id", table_name="calls")
    op.drop_index("idx_calls_agent_fk", table_name="calls")

    op.drop_constraint("fk_calls_organization_id", "calls", type_="foreignkey")
    op.drop_constraint("fk_calls_person_id", "calls", type_="foreignkey")
    op.drop_constraint("fk_calls_agent_fk", "calls", type_="foreignkey")

    op.drop_column("calls", "organization_id")
    op.drop_column("calls", "person_id")
    op.drop_column("calls", "agent_fk")
    op.drop_column("calls", "confidence_score")
    op.drop_column("calls", "resolution")
    op.drop_column("calls", "intent")
    op.drop_column("calls", "entities")

    # Drop FKs from business tables to extracted_facts
    op.drop_constraint("fk_call_product_mentions_fact_id", "call_product_mentions", type_="foreignkey")
    op.drop_constraint("fk_offers_fact_id", "offers", type_="foreignkey")
    op.drop_constraint("fk_tasks_fact_id", "tasks", type_="foreignkey")

    # Drop extracted_facts and indexes
    op.execute("DROP INDEX IF EXISTS uq_extracted_facts_call_type_stable")
    op.drop_index("idx_extracted_facts_fact_type", table_name="extracted_facts")
    op.drop_index("idx_extracted_facts_extraction_id", table_name="extracted_facts")
    op.drop_index("idx_extracted_facts_call_id", table_name="extracted_facts")
    op.drop_table("extracted_facts")

    # Drop business tables
    op.execute("DROP INDEX IF EXISTS uq_call_product_mentions_call_stable_key")
    op.drop_index("idx_call_product_mentions_call_id", table_name="call_product_mentions")
    op.drop_table("call_product_mentions")

    op.execute("DROP INDEX IF EXISTS uq_offers_call_stable_key")
    op.drop_index("idx_offers_call_id", table_name="offers")
    op.drop_table("offers")

    op.execute("DROP INDEX IF EXISTS uq_tasks_call_stable_key")
    op.drop_index("idx_tasks_owner_agent", table_name="tasks")
    op.drop_index("idx_tasks_call_id", table_name="tasks")
    op.drop_table("tasks")

    op.drop_table("products")

    # Drop extractions
    op.drop_index("idx_extractions_call_created", table_name="extractions")
    op.drop_table("extractions")

    # Drop entity_addresses & addresses
    op.drop_index("idx_entity_addresses_organization_id", table_name="entity_addresses")
    op.drop_index("idx_entity_addresses_person_id", table_name="entity_addresses")
    op.drop_table("entity_addresses")

    op.drop_table("addresses")

    # Drop identifiers
    op.drop_index("idx_identifiers_organization_id", table_name="identifiers")
    op.drop_index("idx_identifiers_person_id", table_name="identifiers")
    op.drop_table("identifiers")

    # Drop person_organizations, organizations, people, agents
    op.drop_table("person_organizations")
    op.drop_table("organizations")
    op.drop_table("people")
    op.drop_table("agents")
