import http.server
import socketserver
import sqlite3
import json
import os
import urllib.parse

PORT = 8080
DB_NAME = "soporte_utm.db"

# HTML/CSS/JS interface in a single template for zero-dependency portability
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Panel de Administración | Motor de Soporte IA UTM</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg-dark: #0b0f19;
            --bg-card: #151c2c;
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
            --primary: #6366f1;
            --primary-glow: rgba(99, 102, 241, 0.15);
            --accent-emerald: #10b981;
            --accent-amber: #f59e0b;
            --accent-rose: #f43f5e;
            --border-color: rgba(255, 255, 255, 0.08);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Outfit', sans-serif;
        }

        body {
            background-color: var(--bg-dark);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            overflow-x: hidden;
        }

        header {
            background: rgba(21, 28, 44, 0.6);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--border-color);
            padding: 1.25rem 2rem;
            position: sticky;
            top: 0;
            z-index: 100;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .logo-section {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .logo-indicator {
            width: 12px;
            height: 12px;
            background-color: var(--accent-emerald);
            border-radius: 50%;
            box-shadow: 0 0 12px var(--accent-emerald);
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(0.9); opacity: 0.6; }
            50% { transform: scale(1.1); opacity: 1; }
            100% { transform: scale(0.9); opacity: 0.6; }
        }

        .logo-title {
            font-size: 1.25rem;
            font-weight: 700;
            letter-spacing: 0.5px;
            background: linear-gradient(135deg, #fff 30%, #a5b4fc 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .logo-subtitle {
            font-size: 0.75rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 1.5px;
            margin-top: 2px;
        }

        .container {
            flex: 1;
            max-width: 1400px;
            width: 100%;
            margin: 0 auto;
            padding: 2rem;
        }

        /* Metrics grid */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }

        .metric-card {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.5rem;
            position: relative;
            overflow: hidden;
            transition: all 0.3s ease;
        }

        .metric-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background: var(--primary);
        }

        .metric-card.emerald::before { background: var(--accent-emerald); }
        .metric-card.amber::before { background: var(--accent-amber); }
        .metric-card.rose::before { background: var(--accent-rose); }

        .metric-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(0, 0, 0, 0.2);
            border-color: rgba(255, 255, 255, 0.15);
        }

        .metric-label {
            font-size: 0.875rem;
            color: var(--text-muted);
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .metric-value {
            font-size: 2.25rem;
            font-weight: 700;
            margin: 0.5rem 0 0.25rem 0;
        }

        /* Layout Grid */
        .layout-grid {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 1.5rem;
            margin-bottom: 2rem;
        }

        @media (max-width: 1024px) {
            .layout-grid {
                grid-template-columns: 1fr;
            }
        }

        .card {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.5rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }

        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.5rem;
        }

        .card-title {
            font-size: 1.125rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        /* Custom Tabs/Filters */
        .filter-tabs {
            display: flex;
            gap: 8px;
            overflow-x: auto;
            padding-bottom: 4px;
        }

        .tab-btn {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-color);
            color: var(--text-muted);
            padding: 6px 12px;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .tab-btn:hover {
            background: rgba(255, 255, 255, 0.08);
            color: var(--text-main);
        }

        .tab-btn.active {
            background: var(--primary);
            color: #fff;
            border-color: var(--primary);
            box-shadow: 0 0 10px rgba(99, 102, 241, 0.4);
        }

        /* Tables styling */
        .table-wrapper {
            overflow-x: auto;
            border-radius: 12px;
            border: 1px solid var(--border-color);
        }

        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 0.9rem;
        }

        th {
            background: rgba(255, 255, 255, 0.03);
            color: var(--text-muted);
            padding: 12px 16px;
            font-weight: 600;
            border-bottom: 1px solid var(--border-color);
        }

        td {
            padding: 14px 16px;
            border-bottom: 1px solid var(--border-color);
            color: var(--text-main);
        }

        tr:last-child td {
            border-bottom: none;
        }

        tr:hover td {
            background: rgba(255, 255, 255, 0.01);
        }

        /* Status badges */
        .badge {
            display: inline-flex;
            align-items: center;
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .badge-abierto { background: rgba(245, 158, 11, 0.15); color: var(--accent-amber); }
        .badge-en-proceso { background: rgba(99, 102, 241, 0.15); color: var(--primary); }
        .badge-resuelto { background: rgba(16, 185, 129, 0.15); color: var(--accent-emerald); }
        .badge-escalado { background: rgba(244, 63, 94, 0.15); color: var(--accent-rose); }
        .badge-cerrado { background: rgba(156, 163, 175, 0.15); color: var(--text-muted); }

        .badge-intent {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-color);
            color: var(--text-main);
        }

        /* Modal styling */
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.7);
            backdrop-filter: blur(4px);
            z-index: 1000;
            display: flex;
            align-items: center;
            justify-content: center;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.3s ease;
        }

        .modal-overlay.active {
            opacity: 1;
            pointer-events: auto;
        }

        .modal {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            width: 100%;
            max-width: 600px;
            padding: 2rem;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            transform: scale(0.95);
            transition: transform 0.3s ease;
        }

        .modal-overlay.active .modal {
            transform: scale(1);
        }

        .modal-title {
            font-size: 1.25rem;
            font-weight: 700;
            margin-bottom: 1.5rem;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 0.75rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .close-btn {
            background: none;
            border: none;
            color: var(--text-muted);
            font-size: 1.5rem;
            cursor: pointer;
        }

        .form-group {
            margin-bottom: 1.25rem;
        }

        .form-label {
            display: block;
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-muted);
            margin-bottom: 6px;
            text-transform: uppercase;
        }

        .form-control {
            width: 100%;
            background: rgba(0, 0, 0, 0.2);
            border: 1px solid var(--border-color);
            color: var(--text-main);
            padding: 10px 12px;
            border-radius: 8px;
            font-size: 0.95rem;
        }

        .form-control:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 2px var(--primary-glow);
        }

        .btn {
            background: var(--primary);
            color: #fff;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }

        .btn:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
        }

        .btn-secondary {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-color);
            color: var(--text-main);
        }

        .btn-secondary:hover {
            background: rgba(255, 255, 255, 0.1);
            box-shadow: none;
        }

        /* FAQ table styling */
        .faq-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px;
            border-bottom: 1px solid var(--border-color);
        }

        .faq-item:last-child {
            border-bottom: none;
        }

        .faq-name {
            font-weight: 500;
            font-size: 0.9rem;
            color: var(--text-main);
        }

        .faq-count {
            background: rgba(99, 102, 241, 0.1);
            border: 1px solid rgba(99, 102, 241, 0.3);
            color: var(--primary);
            padding: 2px 8px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
        }

        .search-bar {
            background: rgba(0, 0, 0, 0.2);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 6px 12px;
            color: var(--text-main);
            width: 250px;
            font-size: 0.85rem;
        }
    </style>
</head>
<body>

    <header>
        <div class="logo-section">
            <div class="logo-indicator"></div>
            <div>
                <div class="logo-title">Soporte IA UTM</div>
                <div class="logo-subtitle">Panel de Control Administrativo</div>
            </div>
        </div>
        <div>
            <span style="font-size: 0.85rem; color: var(--text-muted);">Admin: <b>Sistemas UTM</b></span>
        </div>
    </header>

    <div class="container">
        <!-- Metric Cards -->
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">Total de Tickets</div>
                <div class="metric-value" id="m-total">0</div>
            </div>
            <div class="metric-card amber">
                <div class="metric-label">Abiertos / En Proceso</div>
                <div class="metric-value" id="m-pending">0</div>
            </div>
            <div class="metric-card emerald">
                <div class="metric-label">Resueltos / Cerrados</div>
                <div class="metric-value" id="m-resolved">0</div>
            </div>
            <div class="metric-card rose">
                <div class="metric-label">Casos Escalados</div>
                <div class="metric-value" id="m-escalated">0</div>
            </div>
        </div>

        <!-- Layout Grid -->
        <div class="layout-grid">
            <!-- Left: Ticket List -->
            <div class="card">
                <div class="card-header">
                    <div class="card-title">
                        🎫 Gestión de Tickets
                    </div>
                    <input type="text" class="search-bar" id="search-input" placeholder="Buscar por ticket, remitente o asunto..." oninput="filterTickets()">
                </div>
                
                <div style="margin-bottom: 1rem;">
                    <div class="filter-tabs" id="filter-tabs">
                        <button class="tab-btn active" onclick="setFilter('TODOS')">Todos</button>
                        <button class="tab-btn" onclick="setFilter('ABIERTO')">Abiertos</button>
                        <button class="tab-btn" onclick="setFilter('EN_PROCESO')">En Proceso</button>
                        <button class="tab-btn" onclick="setFilter('RESUELTO')">Resueltos</button>
                        <button class="tab-btn" onclick="setFilter('ESCALADO')">Escalados</button>
                        <button class="tab-btn" onclick="setFilter('CERRADO')">Cerrados</button>
                    </div>
                </div>

                <div class="table-wrapper">
                    <table>
                        <thead>
                            <tr>
                                <th>Ticket ID</th>
                                <th>Remitente</th>
                                <th>Asunto</th>
                                <th>Intención</th>
                                <th>Estado</th>
                                <th>Última Actualización</th>
                                <th>Acción</th>
                            </tr>
                        </thead>
                        <tbody id="ticket-table-body">
                            <!-- Dynamically loaded -->
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Right: Analytics and FAQs -->
            <div style="display: flex; flex-direction: column; gap: 1.5rem;">
                <!-- FAQ Analytics Card -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">📈 Top Preguntas Frecuentes</div>
                    </div>
                    <div id="faq-list-container" style="display: flex; flex-direction: column; gap: 4px;">
                        <!-- FAQ Items dynamically loaded -->
                    </div>
                </div>

                <!-- Distribution Chart Card -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">📊 Distribución de Intenciones</div>
                    </div>
                    <div style="position: relative; height: 200px; width: 100%;">
                        <canvas id="intentChart"></canvas>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Edit Ticket Modal -->
    <div class="modal-overlay" id="edit-modal">
        <div class="modal">
            <div class="modal-title">
                <span>Modificar Ticket <span id="modal-ticket-id" style="color: var(--primary);">UTM-XXXXX</span></span>
                <button class="close-btn" onclick="closeModal()">&times;</button>
            </div>
            
            <form id="edit-ticket-form" onsubmit="saveTicket(event)">
                <input type="hidden" id="form-ticket-id">
                
                <div class="form-group">
                    <label class="form-label">Remitente</label>
                    <input type="text" class="form-control" id="form-sender" readonly style="opacity: 0.6;">
                </div>

                <div class="form-group">
                    <label class="form-label">Asunto original</label>
                    <input type="text" class="form-control" id="form-subject" readonly style="opacity: 0.6;">
                </div>

                <div class="form-group">
                    <label class="form-label">Resumen de IA</label>
                    <input type="text" class="form-control" id="form-summary" readonly style="opacity: 0.6;">
                </div>

                <div class="form-group">
                    <label class="form-label">Estado del ticket</label>
                    <select class="form-control" id="form-status">
                        <option value="ABIERTO">Abierto (Pendiente)</option>
                        <option value="EN_PROCESO">En Proceso</option>
                        <option value="RESUELTO">Resuelto (Cierre Exitoso)</option>
                        <option value="ESCALADO">Escalado a Técnico Humano</option>
                        <option value="CERRADO">Cerrado (Transferido/Spam)</option>
                    </select>
                </div>

                <div class="form-group">
                    <label class="form-label">Notas de Resolución / Cierre</label>
                    <textarea class="form-control" id="form-resolution" rows="3" placeholder="Detalla la solución dada a este caso para la auditoría de soporte..."></textarea>
                </div>

                <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 1.5rem;">
                    <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancelar</button>
                    <button type="submit" class="btn">Guardar Cambios</button>
                </div>
            </form>
        </div>
    </div>

    <script>
        let allTickets = [];
        let currentFilter = 'TODOS';
        let chartInstance = null;

        async function loadData() {
            try {
                const response = await fetch('/api/data');
                const data = await response.json();
                
                allTickets = data.tickets;
                
                // Update metrics
                document.getElementById('m-total').innerText = data.metrics.total;
                document.getElementById('m-pending').innerText = data.metrics.pending;
                document.getElementById('m-resolved').innerText = data.metrics.resolved;
                document.getElementById('m-escalated').innerText = data.metrics.escalated;

                // Load FAQs
                const faqContainer = document.getElementById('faq-list-container');
                faqContainer.innerHTML = '';
                if(data.faqs.length === 0) {
                    faqContainer.innerHTML = '<p style="color: var(--text-muted); font-size: 0.9rem; text-align: center; padding: 1rem;">No hay registros de consultas FAQ aún.</p>';
                } else {
                    data.faqs.forEach(faq => {
                        const item = document.createElement('div');
                        item.className = 'faq-item';
                        item.innerHTML = `
                            <span class="faq-name">${faq.resumen}</span>
                            <span class="faq-count">${faq.total} consultas</span>
                        `;
                        faqContainer.appendChild(item);
                    });
                }

                // Render tables and charts
                renderTickets();
                renderChart(data.intent_counts);

            } catch (err) {
                console.error("Error cargando datos:", err);
            }
        }

        function setFilter(filter) {
            currentFilter = filter;
            
            // Toggle active classes on tabs
            const tabs = document.getElementById('filter-tabs').children;
            for(let i=0; i<tabs.length; i++) {
                tabs[i].classList.remove('active');
                if(tabs[i].innerText.toUpperCase().replace(' ', '_') === filter.replace('_', ' ')) {
                    tabs[i].classList.add('active');
                } else if (filter === 'TODOS' && tabs[i].innerText === 'Todos') {
                    tabs[i].classList.add('active');
                }
            }
            renderTickets();
        }

        function filterTickets() {
            renderTickets();
        }

        function renderTickets() {
            const tbody = document.getElementById('ticket-table-body');
            tbody.innerHTML = '';

            const searchQuery = document.getElementById('search-input').value.toLowerCase().trim();

            let filtered = allTickets;

            // Apply tab filter
            if (currentFilter !== 'TODOS') {
                filtered = filtered.filter(t => t.estado === currentFilter);
            }

            // Apply search query
            if (searchQuery) {
                filtered = filtered.filter(t => 
                    t.ticket_id.toLowerCase().includes(searchQuery) ||
                    t.correo.toLowerCase().includes(searchQuery) ||
                    (t.asunto && t.asunto.toLowerCase().includes(searchQuery)) ||
                    (t.resumen && t.resumen.toLowerCase().includes(searchQuery))
                );
            }

            if (filtered.length === 0) {
                tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 2rem;">No se encontraron tickets con los filtros actuales.</td></tr>`;
                return;
            }

            filtered.forEach(t => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><b>${t.ticket_id}</b></td>
                    <td style="max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${t.correo}</td>
                    <td style="max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${t.asunto || 'Sin asunto'}</td>
                    <td><span class="badge badge-intent">${t.intencion}</span></td>
                    <td><span class="badge badge-${t.estado.toLowerCase().replace('_', '-')}">${t.estado}</span></td>
                    <td style="font-size: 0.8rem; color: var(--text-muted);">${t.fecha_actualizado}</td>
                    <td><button class="btn btn-secondary" style="padding: 4px 8px; font-size: 0.8rem;" onclick="openEditModal('${t.ticket_id}')">⚙️ Atender</button></td>
                `;
                tbody.appendChild(tr);
            });
        }

        function renderChart(intentCounts) {
            const ctx = document.getElementById('intentChart').getContext('2d');
            
            const labels = Object.keys(intentCounts);
            const values = Object.values(intentCounts);

            if (chartInstance) {
                chartInstance.destroy();
            }

            chartInstance = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: labels,
                    datasets: [{
                        data: values,
                        backgroundColor: [
                            'rgba(99, 102, 241, 0.7)',  // PASSWORD_RESET
                            'rgba(244, 63, 94, 0.7)',   // ANOMALIA
                            'rgba(245, 158, 11, 0.7)',   // SEGUIMIENTO
                            'rgba(16, 185, 129, 0.7)',  // INFORMACION
                            'rgba(156, 163, 175, 0.7)'  // IGNORAR
                        ],
                        borderColor: 'rgba(21, 28, 44, 1)',
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                color: '#9ca3af',
                                font: { size: 10, family: 'Outfit' }
                            }
                        }
                    }
                }
            });
        }

        function openEditModal(ticketId) {
            const t = allTickets.find(ticket => ticket.ticket_id === ticketId);
            if (!t) return;

            document.getElementById('modal-ticket-id').innerText = t.ticket_id;
            document.getElementById('form-ticket-id').value = t.ticket_id;
            document.getElementById('form-sender').value = t.correo;
            document.getElementById('form-subject').value = t.asunto || '';
            document.getElementById('form-summary').value = t.resumen || '';
            document.getElementById('form-status').value = t.estado;
            document.getElementById('form-resolution').value = t.resolucion || '';

            document.getElementById('edit-modal').classList.add('active');
        }

        function closeModal() {
            document.getElementById('edit-modal').classList.remove('active');
        }

        async function saveTicket(event) {
            event.preventDefault();
            const ticketId = document.getElementById('form-ticket-id').value;
            const estado = document.getElementById('form-status').value;
            const resolucion = document.getElementById('form-resolution').value;

            try {
                const response = await fetch('/api/update', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ticket_id: ticketId, estado, resolucion })
                });

                if(response.ok) {
                    closeModal();
                    loadData();
                } else {
                    alert("Error al actualizar el ticket.");
                }
            } catch(err) {
                console.error(err);
                alert("Error al guardar cambios.");
            }
        }

        // Auto load
        loadData();
    </script>
</body>
</html>
"""

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode('utf-8'))
            
        elif self.path == '/api/data':
            # Query fresh DB state
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            try:
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                
                # Fetch tickets
                cursor.execute("""
                    SELECT ticket_id, correo_origen, fecha_recibido, asunto, intencion, resumen, estado, resolucion, fecha_actualizado
                    FROM tickets 
                    ORDER BY fecha_recibido DESC
                """)
                tickets_raw = cursor.fetchall()
                
                tickets = []
                metrics = {"total": 0, "pending": 0, "resolved": 0, "escalated": 0}
                intent_counts = {}
                
                for r in tickets_raw:
                    ticket_id, correo, fecha, asunto, intencion, resumen, estado, resolucion, fecha_actualizado = r
                    tickets.append({
                        "ticket_id": ticket_id,
                        "correo": correo,
                        "fecha": fecha,
                        "asunto": asunto,
                        "intencion": intencion,
                        "resumen": resumen,
                        "estado": estado,
                        "resolucion": resolucion,
                        "fecha_actualizado": fecha_actualizado
                    })
                    
                    # Accumulate metrics
                    metrics["total"] += 1
                    if estado in ("ABIERTO", "EN_PROCESO"):
                        metrics["pending"] += 1
                    elif estado in ("RESUELTO", "CERRADO"):
                        metrics["resolved"] += 1
                    elif estado == "ESCALADO":
                        metrics["escalated"] += 1
                        
                    # Count intents
                    intent_counts[intencion] = intent_counts.get(intencion, 0) + 1
                
                # Fetch top FAQs
                cursor.execute("""
                    SELECT resumen, COUNT(*) as total 
                    FROM consultas 
                    GROUP BY resumen 
                    ORDER BY total DESC 
                    LIMIT 8
                """)
                faqs = [{"resumen": f[0], "total": f[1]} for f in cursor.fetchall()]
                
                conn.close()
                
                response_data = {
                    "tickets": tickets,
                    "metrics": metrics,
                    "intent_counts": intent_counts,
                    "faqs": faqs
                }
                
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
                
            except Exception as e:
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
        else:
            self.send_error(404, "Page not found")

    def do_POST(self):
        if self.path == '/api/update':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            params = json.loads(post_data.decode('utf-8'))
            
            ticket_id = params.get("ticket_id")
            estado = params.get("estado")
            resolucion = params.get("resolucion")
            
            if ticket_id and estado:
                try:
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE tickets 
                        SET estado = ?, resolucion = ?, fecha_actualizado = CURRENT_TIMESTAMP, 
                            fecha_cerrado = CASE WHEN ? IN ('RESUELTO', 'CERRADO') THEN CURRENT_TIMESTAMP ELSE fecha_cerrado END
                        WHERE ticket_id = ?
                    """, (estado, resolucion, estado, ticket_id))
                    conn.commit()
                    conn.close()
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "success"}).encode('utf-8'))
                except Exception as e:
                    self.send_response(500)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
            else:
                self.send_error(400, "Missing parameters")

def start_server():
    # Use socketserver to avoid port in use errors when binding
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), DashboardHandler) as httpd:
        print(f"\n=======================================================")
        print(f"🚀 PANEL DE ADMINISTRACIÓN - SOPORTE IA UTM ACTIVO")
        print(f"🔗 Abre tu navegador en: http://localhost:{PORT}")
        print(f"=======================================================\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor administrativo detenido.")

if __name__ == "__main__":
    start_server()
