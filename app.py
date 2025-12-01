import os
from pathlib import Path
from typing import Dict, List
from flask import Flask, render_template, request, redirect, url_for, flash

from database import close_db, get_db, init_db, recalculate_month_totals


def create_app(test_config: Dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY='dev',
        DATABASE=Path(app.instance_path) / 'payroll.sqlite',
    )

    if test_config:
        app.config.update(test_config)

    # Garanta que a pasta instance exista (Atualizar se necessário).
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    @app.teardown_appcontext
    def teardown_db(exception=None):
        close_db()

    with app.app_context():
        init_db(app)

    register_routes(app)
    return app


def register_routes(app: Flask) -> None:
    @app.route('/')
    def dashboard():
        db = get_db(app)
        totals = db.execute(
            "SELECT period, total_proventos, total_descontos, valor_liquido FROM monthly_totals ORDER BY period"
        ).fetchall()

        recent = db.execute(
            "SELECT period, total_proventos, total_descontos, valor_liquido FROM monthly_totals ORDER BY period DESC LIMIT 1"
        ).fetchone()

        return render_template('dashboard.html', totals=totals, recent=recent)

    @app.route('/details', methods=['GET', 'POST'])
    def details():
        db = get_db(app)
        if request.method == 'POST':
            period = request.form['period']
            description = request.form['description']
            entry_type = request.form['entry_type']
            amount = float(request.form['amount'])
            db.execute(
                "INSERT INTO detail_entries (period, description, entry_type, amount) VALUES (?, ?, ?, ?)",
                (period, description, entry_type, amount),
            )
            db.commit()
            recalculate_month_totals(app, period)
            flash('Lançamento adicionado com sucesso!', 'success')
            return redirect(url_for('details'))

        entries = db.execute(
            "SELECT id, period, description, entry_type, amount, created_at FROM detail_entries ORDER BY period DESC, id DESC"
        ).fetchall()
        return render_template('details.html', entries=entries)

    @app.route('/details/<int:entry_id>/edit', methods=['GET', 'POST'])
    def edit_entry(entry_id):
        db = get_db(app)
        entry = db.execute(
            "SELECT id, period, description, entry_type, amount FROM detail_entries WHERE id = ?",
            (entry_id,),
        ).fetchone()
        if entry is None:
            flash('Registro não encontrado.', 'danger')
            return redirect(url_for('details'))

        if request.method == 'POST':
            old_period = entry['period']
            period = request.form['period']
            description = request.form['description']
            entry_type = request.form['entry_type']
            amount = float(request.form['amount'])
            db.execute(
                "UPDATE detail_entries SET period = ?, description = ?, entry_type = ?, amount = ? WHERE id = ?",
                (period, description, entry_type, amount, entry_id),
            )
            db.commit()
            recalculate_month_totals(app, period)
            if old_period != period:
                recalculate_month_totals(app, old_period)
            flash('Lançamento atualizado!', 'success')
            return redirect(url_for('details'))

        return render_template('edit.html', entry=entry)

    @app.route('/details/<int:entry_id>/delete', methods=['POST'])
    def delete_entry(entry_id):
        db = get_db(app)
        entry = db.execute(
            "SELECT period FROM detail_entries WHERE id = ?",
            (entry_id,),
        ).fetchone()
        if entry:
            db.execute("DELETE FROM detail_entries WHERE id = ?", (entry_id,))
            db.commit()
            recalculate_month_totals(app, entry['period'])
            flash('Lançamento removido!', 'success')
        else:
            flash('Registro não encontrado.', 'danger')
        return redirect(url_for('details'))

    @app.route('/queries', methods=['GET'])
    def queries():
        db = get_db(app)
        period = request.args.get('period')
        entry_type = request.args.get('entry_type')
        query = "SELECT period, description, entry_type, amount, created_at FROM detail_entries"
        filters: List[str] = []
        params: List[str] = []

        if period:
            filters.append('period = ?')
            params.append(period)
        if entry_type:
            filters.append('entry_type = ?')
            params.append(entry_type)
        if filters:
            query += " WHERE " + " AND ".join(filters)
        query += " ORDER BY period DESC, created_at DESC"

        entries = db.execute(query, params).fetchall()

        totals_query = "SELECT period, total_proventos, total_descontos, valor_liquido FROM monthly_totals ORDER BY period DESC"
        totals = db.execute(totals_query).fetchall()
        return render_template('queries.html', entries=entries, totals=totals)

    @app.route('/totals')
    def totals():
        db = get_db(app)
        totals = db.execute(
            "SELECT period, total_proventos, total_descontos, valor_liquido FROM monthly_totals ORDER BY period DESC"
        ).fetchall()
        return render_template('totals.html', totals=totals)


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
