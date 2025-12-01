import os
from datetime import datetime
from collections import defaultdict

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

# Keep this comment aligned with business rules; update it whenever the data model or
# reconciliation logic changes so future agents understand the intent of each table.
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "data", "payroll.db")

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DATABASE_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = "change-me-in-production"

db = SQLAlchemy(app)


class PayrollItem(db.Model):
    __tablename__ = "payroll_items"

    id = db.Column(db.Integer, primary_key=True)
    month = db.Column(db.String(7), index=True, nullable=False)  # YYYY-MM
    subject = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    reference = db.Column(db.String(120), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    item_type = db.Column(db.String(20), nullable=False)  # provento, desconto, outro
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class MonthlyTotal(db.Model):
    __tablename__ = "monthly_totals"

    id = db.Column(db.Integer, primary_key=True)
    month = db.Column(db.String(7), unique=True, nullable=False)
    total_proventos = db.Column(db.Float, default=0.0, nullable=False)
    total_descontos = db.Column(db.Float, default=0.0, nullable=False)
    valor_liquido = db.Column(db.Float, default=0.0, nullable=False)
    notes = db.Column(db.String(255), nullable=True)


def ensure_database_ready() -> None:
    """Create the SQLite file, tables, and seed data if nothing exists."""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    db.create_all()
    if not PayrollItem.query.first():
        seed_demo_data()


def seed_demo_data() -> None:
    """Insert illustrative rows for local testing; adjust/remove when real data arrives."""
    demo_items = [
        PayrollItem(
            month="2025-01",
            subject="Folha Mensal",
            description="Salário Base",
            reference="220h",
            amount=7200.00,
            item_type="provento",
        ),
        PayrollItem(
            month="2025-01",
            subject="Folha Mensal",
            description="INSS",
            reference=None,
            amount=-850.15,
            item_type="desconto",
        ),
        PayrollItem(
            month="2025-01",
            subject="Horas Extras",
            description="HE 50%",
            reference="12h",
            amount=840.50,
            item_type="provento",
        ),
        PayrollItem(
            month="2025-02",
            subject="Folha Mensal",
            description="Salário Base",
            reference="220h",
            amount=7200.00,
            item_type="provento",
        ),
        PayrollItem(
            month="2025-02",
            subject="Folha Mensal",
            description="Imposto de Renda",
            reference=None,
            amount=-1120.33,
            item_type="desconto",
        ),
        PayrollItem(
            month="2025-02",
            subject="Outros",
            description="PLR Parcial",
            reference=None,
            amount=1500.00,
            item_type="provento",
        ),
    ]
    db.session.bulk_save_objects(demo_items)
    db.session.commit()
    reconcile_monthly_totals()


def reconcile_monthly_totals() -> None:
    """Rebuild the monthly_totals table from payroll_items, keeping manual notes."""
    notes_map = {total.month: total.notes for total in MonthlyTotal.query.all()}
    aggregates = defaultdict(lambda: {"proventos": 0.0, "descontos": 0.0})

    for month, item_type, total in (
        db.session.query(PayrollItem.month, PayrollItem.item_type, func.sum(PayrollItem.amount))
        .group_by(PayrollItem.month, PayrollItem.item_type)
        .all()
    ):
        if item_type == "provento":
            aggregates[month]["proventos"] += float(total or 0)
        elif item_type == "desconto":
            aggregates[month]["descontos"] += abs(float(total or 0))
        else:
            aggregates[month]["proventos"] += float(total or 0)

    MonthlyTotal.query.delete()
    for month, values in aggregates.items():
        proventos = values["proventos"]
        descontos = values["descontos"]
        liquid = proventos - descontos
        db.session.add(
            MonthlyTotal(
                month=month,
                total_proventos=round(proventos, 2),
                total_descontos=round(descontos, 2),
                valor_liquido=round(liquid, 2),
                notes=notes_map.get(month),
            )
        )
    db.session.commit()


@app.route("/")
def index():
    ensure_database_ready()
    reconcile_monthly_totals()

    items = PayrollItem.query.order_by(PayrollItem.month.desc(), PayrollItem.id.desc()).all()
    totals = MonthlyTotal.query.order_by(MonthlyTotal.month.desc()).all()

    filter_month = request.args.get("filter_month")
    filter_type = request.args.get("filter_type")
    query_results = query_items(filter_month, filter_type)

    dashboard_data = build_dashboard_data(totals)
    months = sorted({item.month for item in items}, reverse=True)

    return render_template(
        "index.html",
        items=items,
        totals=totals,
        months=months,
        query_results=query_results,
        selected_month=filter_month or "",
        selected_type=filter_type or "",
        dashboard_data=dashboard_data,
    )


def query_items(filter_month: str | None, filter_type: str | None):
    query = PayrollItem.query
    if filter_month:
        query = query.filter(PayrollItem.month == filter_month)
    if filter_type:
        query = query.filter(PayrollItem.item_type == filter_type)
    return query.order_by(PayrollItem.month.desc(), PayrollItem.id.desc()).all()


@app.route("/items", methods=["POST"])
def create_item():
    ensure_database_ready()
    month = request.form.get("month")
    subject = request.form.get("subject")
    description = request.form.get("description")
    reference = request.form.get("reference")
    amount = float(request.form.get("amount"))
    item_type = request.form.get("item_type")

    new_item = PayrollItem(
        month=month,
        subject=subject,
        description=description,
        reference=reference,
        amount=amount,
        item_type=item_type,
    )
    db.session.add(new_item)
    db.session.commit()
    reconcile_monthly_totals()
    flash("Item adicionado com sucesso.", "success")
    return redirect(url_for("index"))


@app.route("/items/<int:item_id>/update", methods=["POST"])
def update_item(item_id: int):
    ensure_database_ready()
    item = PayrollItem.query.get_or_404(item_id)
    item.month = request.form.get("month")
    item.subject = request.form.get("subject")
    item.description = request.form.get("description")
    item.reference = request.form.get("reference")
    item.amount = float(request.form.get("amount"))
    item.item_type = request.form.get("item_type")
    db.session.commit()
    reconcile_monthly_totals()
    flash("Item atualizado com sucesso.", "success")
    return redirect(url_for("index"))


@app.route("/items/<int:item_id>/delete", methods=["POST"])
def delete_item(item_id: int):
    ensure_database_ready()
    item = PayrollItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    reconcile_monthly_totals()
    flash("Item excluído.", "info")
    return redirect(url_for("index"))


@app.route("/totals", methods=["POST"])
def create_total():
    ensure_database_ready()
    month = request.form.get("month")
    total_proventos = float(request.form.get("total_proventos"))
    total_descontos = float(request.form.get("total_descontos"))
    notes = request.form.get("notes")

    existing = MonthlyTotal.query.filter_by(month=month).first()
    if existing:
        flash("Já existe um total para este mês. Edite ao invés de criar.", "warning")
        return redirect(url_for("index"))

    valor_liquido = total_proventos - total_descontos
    total = MonthlyTotal(
        month=month,
        total_proventos=total_proventos,
        total_descontos=total_descontos,
        valor_liquido=valor_liquido,
        notes=notes,
    )
    db.session.add(total)
    db.session.commit()
    flash("Total mensal adicionado.", "success")
    return redirect(url_for("index"))


@app.route("/totals/<int:total_id>/update", methods=["POST"])
def update_total(total_id: int):
    ensure_database_ready()
    total = MonthlyTotal.query.get_or_404(total_id)
    total.month = request.form.get("month")
    total.total_proventos = float(request.form.get("total_proventos"))
    total.total_descontos = float(request.form.get("total_descontos"))
    total.valor_liquido = total.total_proventos - total.total_descontos
    total.notes = request.form.get("notes")
    db.session.commit()
    flash("Total mensal atualizado.", "success")
    return redirect(url_for("index"))


@app.route("/totals/<int:total_id>/delete", methods=["POST"])
def delete_total(total_id: int):
    ensure_database_ready()
    total = MonthlyTotal.query.get_or_404(total_id)
    db.session.delete(total)
    db.session.commit()
    flash("Total mensal excluído.", "info")
    return redirect(url_for("index"))


@app.route("/totals/recalculate", methods=["POST"])
def recalculate_totals():
    ensure_database_ready()
    reconcile_monthly_totals()
    flash("Totais recalculados a partir dos itens.", "success")
    return redirect(url_for("index"))


def build_dashboard_data(totals):
    sorted_totals = sorted(totals, key=lambda t: t.month)
    series = {
        "months": [t.month for t in sorted_totals],
        "proventos": [t.total_proventos for t in sorted_totals],
        "descontos": [t.total_descontos for t in sorted_totals],
        "liquido": [t.valor_liquido for t in sorted_totals],
    }
    latest = sorted_totals[-1] if sorted_totals else None
    return {"series": series, "latest": latest}


if __name__ == "__main__":
    ensure_database_ready()
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
