"""add_kompas_destination_town

Revision ID: 32e277c4d2d4
Revises: ZZZZ_samo_departure_city
Create Date: 2026-06-23 21:01:27.671254

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '32e277c4d2d4'
down_revision: Union[str, None] = 'ZZZZ_samo_departure_city'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('kompas_destination_town',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('town_id', sa.BigInteger(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('country_id', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['country_id'], ['kompas_country.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('kompas_destination_town')