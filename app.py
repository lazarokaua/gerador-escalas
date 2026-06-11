import io
import os
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from escala_engine import ScaleEngine

# Set up page configurations
st.set_page_config(
    page_title="Gerador de Escala de Esteiras",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply some custom CSS for a premium feel and print layout styling
st.markdown("""
    <style>
        .stButton>button {
            border-radius: 8px;
            font-weight: 500;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 24px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            white-space: pre-wrap;
            font-weight: 600;
            font-size: 16px;
        }
        .header-title {
            font-family: 'Inter', sans-serif;
            font-weight: 800;
            background: linear-gradient(45deg, #FF4B4B, #FF8F8F);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
        }
        
        /* Hide the print table template during screen viewing */
        .print-only {
            display: none !important;
        }
        
        /* Print-specific stylesheet rules */
        @media print {
            /* Hide general layout wrappers, menu, footers and tabs of Streamlit */
            header, 
            footer, 
            [data-testid="stSidebar"], 
            [data-testid="stToolbar"], 
            [data-testid="stMarkdownDivider"],
            div[data-baseweb="tab-list"],
            hr {
                display: none !important;
            }
            
            /* Hide horizontal block layouts (like metrics grid and button columns) */
            [data-testid="stHorizontalBlock"] {
                display: none !important;
            }
            
            /* Hide all standard element containers on the page */
            [data-testid="element-container"] {
                display: none !important;
            }
            
            /* Exclude only the element container holding the printable scale table */
            [data-testid="element-container"]:has(.print-only) {
                display: block !important;
            }
            
            /* Maximize printable area container width and remove top padding */
            .main .block-container {
                padding: 0 !important;
                margin: 0 !important;
                max-width: 100% !important;
                width: 100% !important;
            }
            
            /* Make print-only block visible and format layout */
            .print-only {
                display: block !important;
                width: 100% !important;
                color: #000000 !important;
                background-color: #ffffff !important;
            }
            
            .print-only h3 {
                color: #000000 !important;
                font-family: Arial, sans-serif !important;
                margin-top: 0 !important;
                margin-bottom: 5px !important;
                text-align: center !important;
            }
            
            /* High resolution table formatting for printed papers */
            .print-table {
                width: 100% !important;
                border-collapse: collapse !important;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif !important;
                font-size: 11pt !important;
                color: #000000 !important;
            }
            .print-table th, .print-table td {
                border: 1px solid #333333 !important;
                padding: 10px 8px !important;
                text-align: center !important;
            }
            .print-table th {
                background-color: #e9ecef !important;
                font-weight: bold !important;
            }
            .print-table td {
                background-color: #ffffff !important;
            }
            
            /* Set print page options */
            @page {
                size: landscape;
                margin: 1cm;
            }
        }
    </style>
""", unsafe_allow_html=True)

# Always create a fresh engine on each run to guarantee the latest config
# from disk is used (config changes are persisted immediately via save_config).
engine: ScaleEngine = ScaleEngine()

# Header section
st.markdown('<h1 class="header-title">📅 Gerador de Escala Semanal</h1>', unsafe_allow_html=True)
st.write("Gerencie a equipe, setores e gere a escala rotativa de forma dinâmica e automatizada.")
st.divider()

# Create tabs for scale generation, team management, and sector management
tab_scale, tab_team, tab_sectors = st.tabs([
    "📅 Gerar Escala", 
    "👥 Gerenciar Equipe", 
    "🏢 Gerenciar Setores"
])

# ----------------- TAB: GENERATE SCALE -----------------
with tab_scale:
    st.header("Visualização e Geração")
    
    current_week = datetime.now().isocalendar()[1]
    default_week = current_week + 1 if current_week < 52 else 1
    
    col_week, col_info = st.columns([1, 2])
    
    with col_week:
        week_number = st.number_input(
            "Número da Semana", 
            min_value=1, 
            max_value=53, 
            value=default_week,
            step=1,
            help="Escolha o número da semana do ano para a qual deseja gerar a escala."
        )
        
        # Calculate start and end dates of the week
        current_year = datetime.now().year
        try:
            start_date = datetime.fromisocalendar(current_year, int(week_number), 1)
            end_date = start_date + timedelta(days=5)
            date_range_str = f"Escala de {start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}"
            st.info(date_range_str)
        except Exception:
            st.error("Número de semana inválido para este ano.")
            
    with col_info:
        # Mini metrics summary
        total_team = len(engine.team)
        total_capacity = sum(s["capacity"] for s in engine.sectors if s["name"] != "APOIO")
        has_apoio = any(s["name"] == "APOIO" for s in engine.sectors)
        
        st.write("### Resumo das Configurações Atuais")
        metric_col1, metric_col2, metric_col3 = st.columns(3)
        metric_col1.metric("Total de Colaboradores", total_team)
        metric_col2.metric("Vagas diárias necessárias", total_capacity)
        metric_col3.metric("Possui Apoio Semanal?", "Sim" if has_apoio else "Não")
        
        if total_team < (total_capacity + (1 if has_apoio else 0)):
            st.warning("⚠️ Atenção: O número de colaboradores na equipe é inferior à capacidade total necessária dos setores. Alguns setores podem ficar sem preenchimento.")

    st.write("---")

    if st.button("🚀 Gerar e Visualizar Escala", type="primary", use_container_width=True):
        if not engine.team:
            st.error("A equipe está vazia. Adicione colaboradores na aba 'Gerenciar Equipe' primeiro.")
        elif not engine.sectors:
            st.error("Não há setores configurados. Adicione pelo menos um setor na aba 'Gerenciar Setores'.")
        else:
            try:
                # Generate scale data
                scale_data = engine.generate_scale(int(week_number))
                df = pd.DataFrame(scale_data)
                
                # Display Scale DataFrame in Streamlit
                st.subheader(f"📅 Escala Gerada - Semana {week_number}")
                st.dataframe(df, width="stretch")
                
                # High-resolution static HTML table for printing (hidden on screen, visible on print)
                html_table = df.to_html(classes="print-table", index=False)
                html_table_raw = html_table.replace("\n", "").replace("'", "\\'")
                st.markdown(
                    f'<div class="print-only">'
                    f'<h3>📅 Escala - Semana {week_number}</h3>'
                    f'<p style="text-align: center; font-style: italic; margin-top: -10px;">{date_range_str}</p>'
                    f'{html_table}'
                    f'</div>', 
                    unsafe_allow_html=True
                )
                
                # Save locally (mirroring CustomTkinter behavior)
                try:
                    local_path = engine.export_to_excel(scale_data, int(week_number))
                    st.success(f"💾 Arquivo salvo localmente em: `{local_path}`")
                except Exception as e:
                    st.warning(f"Não foi possível salvar localmente na pasta Downloads: {e}")
                
                # Provide in-memory Excel download option for the user's browser
                excel_buffer = io.BytesIO()
                sheet_name = f"ESCALA {start_date.strftime('%d-%m')} A {end_date.strftime('%d-%m')}"
                
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name=sheet_name)
                
                excel_bytes = excel_buffer.getvalue()
                
                col_download, col_print = st.columns(2)
                
                with col_download:
                    st.download_button(
                        label="📥 Baixar Planilha Excel",
                        data=excel_bytes,
                        file_name=f"escala_semana_{week_number}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                    
                with col_print:
                    components.html(f"""
                        <body style="margin: 0; padding: 0; background: transparent; overflow: hidden;">
                            <button id="print-btn" style="
                                display: inline-flex;
                                align-items: center;
                                justify-content: center;
                                background-color: transparent;
                                border: 1px solid rgba(128, 128, 128, 0.3);
                                padding: 0px 16px;
                                border-radius: 8px;
                                font-weight: 500;
                                font-size: 16px;
                                width: 100%;
                                height: 38px;
                                cursor: pointer;
                                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                                box-sizing: border-box;
                            ">🖨️ Imprimir Escala</button>
                            <script>
                                try {{
                                    var parentBody = window.parent.document.body;
                                    var style = window.parent.getComputedStyle(parentBody);
                                    var textColor = style.color;
                                    var btn = document.getElementById('print-btn');
                                    btn.style.color = textColor;
                                    if (textColor.indexOf('250') !== -1 || textColor.indexOf('255') !== -1 || textColor.indexOf('fafafa') !== -1) {{
                                        btn.style.borderColor = 'rgba(250, 250, 250, 0.2)';
                                    }} else {{
                                        btn.style.borderColor = 'rgba(49, 51, 63, 0.2)';
                                    }}
                                }} catch (e) {{
                                    document.getElementById('print-btn').style.color = '#31333F';
                                }}
                                
                                document.getElementById('print-btn').onclick = function() {{
                                    var printWindow = window.open('', '_blank');
                                    var htmlContent = `
                                        <html>
                                            <head>
                                                <title>Escala Semana {week_number}</title>
                                                <style>
                                                    body {{
                                                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                                                        margin: 30px;
                                                        background-color: #ffffff;
                                                        color: #000000;
                                                    }}
                                                    h3 {{
                                                        text-align: center;
                                                        margin-bottom: 5px;
                                                        font-size: 18pt;
                                                    }}
                                                    p {{
                                                        text-align: center;
                                                        font-style: italic;
                                                        margin-top: 0;
                                                        margin-bottom: 25px;
                                                        font-size: 12pt;
                                                    }}
                                                    table {{
                                                        width: 100%;
                                                        border-collapse: collapse;
                                                        margin-top: 10px;
                                                    }}
                                                    th, td {{
                                                        border: 1px solid #333333;
                                                        padding: 12px 10px;
                                                        text-align: center;
                                                        font-size: 11pt;
                                                    }}
                                                    th {{
                                                        background-color: #f2f2f2;
                                                        font-weight: bold;
                                                    }}
                                                    @media print {{
                                                        @page {{
                                                            size: landscape;
                                                            margin: 1cm;
                                                        }}
                                                    }}
                                                </style>
                                            </head>
                                            <body>
                                                <h3>📅 Escala - Semana {week_number}</h3>
                                                <p style="text-align: center; font-style: italic; margin-top: -10px;">{date_range_str}</p>
                                                {html_table_raw}
                                                <script>
                                                    window.onload = function() {{
                                                        window.print();
                                                        setTimeout(function() {{
                                                            window.close();
                                                        }}, 500);
                                                    }};
                                                <\\/script>
                                            </body>
                                        </html>
                                    `;
                                    printWindow.document.write(htmlContent);
                                    printWindow.document.close();
                                }}
                            </script>
                        </body>
                    """, height=38)
                
            except Exception as e:
                st.error(f"Erro ao gerar escala: {e}")

# ----------------- TAB: MANAGE TEAM -----------------
with tab_team:
    st.header("Gerenciamento de Colaboradores")
    
    col_list, col_actions = st.columns([1, 1])
    
    with col_list:
        st.subheader("Lista da Equipe")
        if engine.team:
            # Display current team list as a table for better visualization
            team_df = pd.DataFrame({"Ordem de Rotação": range(1, len(engine.team) + 1), "Nome": engine.team})
            st.dataframe(team_df, width="stretch", hide_index=True)
        else:
            st.info("Nenhum colaborador cadastrado.")
            
    with col_actions:
        st.subheader("Ações")
        
        # Add new collaborator form
        with st.form("add_member_form", clear_on_submit=True):
            new_member = st.text_input("Nome do Colaborador").strip().upper()
            submit_add = st.form_submit_button("➕ Adicionar Colaborador")
            
            if submit_add:
                if not new_member:
                    st.error("Por favor, digite um nome.")
                elif new_member in engine.team:
                    st.error(f"O colaborador '{new_member}' já está na equipe.")
                else:
                    updated_team = engine.team + [new_member]
                    engine.save_config(updated_team, engine.sectors)
                    st.success(f"'{new_member}' adicionado com sucesso!")
                    st.rerun()
        
        st.write("---")
        
        # Remove collaborator form
        if engine.team:
            with st.form("remove_member_form"):
                member_to_remove = st.selectbox("Selecione o Colaborador para Remover", engine.team)
                submit_remove = st.form_submit_button("🗑️ Remover Colaborador")
                
                if submit_remove:
                    updated_team = [m for m in engine.team if m != member_to_remove]
                    engine.save_config(updated_team, engine.sectors)
                    st.success(f"'{member_to_remove}' removido com sucesso!")
                    st.rerun()

# ----------------- TAB: MANAGE SECTORS -----------------
with tab_sectors:
    st.header("Gerenciamento de Setores e Capacidades")
    
    col_list_sec, col_actions_sec = st.columns([1, 1])
    
    with col_list_sec:
        st.subheader("Lista de Setores")
        if engine.sectors:
            sectors_df = pd.DataFrame(engine.sectors)
            sectors_df.columns = ["Nome do Setor", "Capacidade (Pessoas)"]
            st.dataframe(sectors_df, width="stretch", hide_index=True)
        else:
            st.info("Nenhum setor cadastrado.")
            
    with col_actions_sec:
        st.subheader("Ações")
        
        # Add new sector form
        with st.form("add_sector_form", clear_on_submit=True):
            new_sector_name = st.text_input("Nome do Setor").strip().upper()
            capacity = st.number_input("Quantidade de Colaboradores", min_value=1, max_value=10, value=1, step=1)
            submit_add_sec = st.form_submit_button("➕ Adicionar Setor")
            
            if submit_add_sec:
                if not new_sector_name:
                    st.error("Por favor, digite o nome do setor.")
                elif any(s["name"] == new_sector_name for s in engine.sectors):
                    st.error(f"O setor '{new_sector_name}' já está cadastrado.")
                else:
                    updated_sectors = engine.sectors + [{"name": new_sector_name, "capacity": capacity}]
                    engine.save_config(engine.team, updated_sectors)
                    st.success(f"Setor '{new_sector_name}' com capacidade {capacity} adicionado!")
                    st.rerun()
                    
        st.write("---")
        
        # Remove sector form
        if engine.sectors:
            with st.form("remove_sector_form"):
                sector_names = [s["name"] for s in engine.sectors]
                sector_to_remove = st.selectbox("Selecione o Setor para Remover", sector_names)
                submit_remove_sec = st.form_submit_button("🗑️ Remover Setor")
                
                if submit_remove_sec:
                    updated_sectors = [s for s in engine.sectors if s["name"] != sector_to_remove]
                    engine.save_config(engine.team, updated_sectors)
                    st.success(f"Setor '{sector_to_remove}' removido com sucesso!")
                    st.rerun()
