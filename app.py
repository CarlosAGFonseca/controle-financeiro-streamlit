# app.py
import streamlit as st
import pandas as pd
import io
import datetime
import plotly.express as px

from st_aggrid import AgGrid, GridOptionsBuilder, DataReturnMode, GridUpdateMode

st.set_page_config(page_title="FinTrack - Controle Financeiro", layout="wide")
st.title("FinTrack — Controle Financeiro (MVP)")

# -------------------------
# Helpers
# -------------------------
def default_df():
    cols = [
        "ID", "Data", "Mês", "Tipo (Receita/Despesa)", "Descrição", "Categoria",
        "Valor Total (R$)", "Forma de Pagamento", "Nº Parcelas", "Parcela Atual",
        "Valor Parcela (R$)", "Pago (Sim/Não)", "Tipo de Custo (Fixa/Variável)",
        "Previsão (Sim/Não)", "Observações"
    ]
    return pd.DataFrame(columns=cols)

def df_to_excel_bytes(df: pd.DataFrame):
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Lançamentos", index=False)
    out.seek(0)
    return out.read()

def ensure_columns(df: pd.DataFrame):
    # Garante colunas esperadas e ordem
    base = default_df()
    for c in base.columns:
        if c not in df.columns:
            df[c] = ""
    return df[base.columns]

# -------------------------
# Layout lateral (inputs)
# -------------------------
with st.sidebar:
    st.header("Ações")
    uploaded_file = st.file_uploader("📁 Upload da planilha (.xlsx)", type=["xlsx"])
    if st.button("🔄 Resetar tabela (limpar)"):
    confirmar_limpeza = st.button("Tenho certeza que quero limpar")
    if confirmar_limpeza:
        st.session_state.pop("df", None)
        st.success("Tabela limpa com sucesso!")
    st.markdown("---")
    st.info("Dica: edite valores diretamente na tabela abaixo. Use o botão 'Adicionar linha' para inserir rápido.")

# -------------------------
# Carregar / Inicializar DF
# -------------------------
if "df" not in st.session_state:
    if uploaded_file is not None:
        try:
            df = pd.read_excel(uploaded_file, sheet_name="Lançamentos")
            df = ensure_columns(df)
            # Converter Data para datetime quando possível
            if "Data" in df.columns:
                df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
        except Exception as e:
            st.error(f"Erro lendo arquivo: {e}")
            df = default_df()
    else:
        df = default_df()
    st.session_state.df = df
else:
    # se já tem df na sessão, atualiza caso user faça upload novo arquivo
    if uploaded_file is not None and st.session_state.get("last_upload") != uploaded_file:
        try:
            df = pd.read_excel(uploaded_file, sheet_name="Lançamentos")
            df = ensure_columns(df)
            df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
            st.session_state.df = df
            st.session_state.last_upload = uploaded_file
            st.success("Arquivo carregado e substituiu a tabela temporária.")
        except Exception as e:
            st.error(f"Erro lendo arquivo: {e}")

df = st.session_state.df

# -------------------------
# Top bar — quick add
# -------------------------
st.subheader("➕ Adicionar lançamento rápido")
with st.form(key="add_form", clear_on_submit=True):
    col1, col2, col3 = st.columns([2,2,2])
    data_input = col1.date_input("Data", value=datetime.date.today())
    tipo_input = col2.selectbox("Tipo", ["Despesa", "Receita"])
    categoria_input = col3.text_input("Categoria", value="")
    descricao_input = st.text_input("Descrição", value="")
    valor_input = st.number_input("Valor Total (R$)", min_value=0.0, format="%.2f")
    forma_input = st.selectbox("Forma de Pagamento", ["Cartão", "Pix", "Dinheiro", "Boleto", "Débito", "Transferência"])
    parcelas_input = st.number_input("Nº Parcelas", min_value=1, value=1, step=1)
    parcela_atual_input = st.number_input("Parcela Atual", min_value=1, value=1, step=1)
    pago_input = st.selectbox("Pago?", ["Sim", "Não"])
    tipo_custo_input = st.selectbox("Tipo de Custo", ["Fixa", "Variável"])
    previsao_input = st.selectbox("Previsão?", ["Não", "Sim"])
    obs_input = st.text_input("Observações", value="")

    submit = st.form_submit_button("Adicionar")
    if submit:
        new_id = int(df["ID"].max()) + 1 if not df.empty and pd.to_numeric(df["ID"], errors="coerce").notnull().any() else 1
        new_row = {
            "ID": new_id,
            "Data": pd.to_datetime(data_input),
            "Mês": pd.to_datetime(data_input).strftime("%B"),
            "Tipo (Receita/Despesa)": tipo_input,
            "Descrição": descricao_input,
            "Categoria": categoria_input,
            "Valor Total (R$)": float(valor_input),
            "Forma de Pagamento": forma_input,
            "Nº Parcelas": int(parcelas_input),
            "Parcela Atual": int(parcela_atual_input),
            "Valor Parcela (R$)": float(valor_input) / int(parcelas_input) if parcelas_input and parcelas_input>0 else float(valor_input),
            "Pago (Sim/Não)": pago_input,
            "Tipo de Custo (Fixa/Variável)": tipo_custo_input,
            "Previsão (Sim/Não)": previsao_input,
            "Observações": obs_input
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        st.session_state.df = ensure_columns(df)
        st.success("Lançamento adicionado.")

# -------------------------
# Tabela editável com st_aggrid
# -------------------------
st.subheader("🧾 Tabela de Lançamentos (edite direto)")

# Prepara df para exibir (copiar para evitar mutações indesejadas)
display_df = st.session_state.df.copy()
# Formatar datas para exibição
if "Data" in display_df.columns:
    display_df["Data"] = display_df["Data"].dt.date.astype(str)

# Configurar AgGrid
gb = GridOptionsBuilder.from_dataframe(display_df)
gb.configure_default_column(editable=True, resizable=True, filter=True)
# Colunas específicas como tipo numérico
gb.configure_column("Valor Total (R$)", type=["numericColumn","numberColumnFilter","customCurrencyFormat"])
gb.configure_column("Valor Parcela (R$)", type=["numericColumn","numberColumnFilter","customCurrencyFormat"])
gb.configure_selection(selection_mode="multiple", use_checkbox=True)
grid_options = gb.build()

grid_response = AgGrid(
    display_df,
    gridOptions=grid_options,
    height=300,
    data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
    update_mode=GridUpdateMode.MODEL_CHANGED,
    fit_columns_on_grid_load=True,
    allow_unsafe_jscode=True
)

# Recupera o DataFrame atualizado pelo AgGrid
updated_df = pd.DataFrame(grid_response["data"])
# Reconverte Data coluna se estiver como string
if "Data" in updated_df.columns:
    try:
        updated_df["Data"] = pd.to_datetime(updated_df["Data"], errors="coerce")
    except:
        pass

# Botões para ações sobre a tabela
col_a, col_b, col_c = st.columns([1,1,2])
with col_a:
    if st.button("🔁 Salvar alterações (sessão)"):
        st.session_state.df = ensure_columns(updated_df)
        st.success("Alterações salvas na sessão.")
with col_b:
    if st.button("🗑️ Remover linhas selecionadas"):
        selected = grid_response.get("selected_rows", [])
        if selected:
            sel_df = pd.DataFrame(selected)
            # remove por ID se existir
            if "ID" in st.session_state.df.columns:
                ids = sel_df["ID"].tolist()
                st.session_state.df = st.session_state.df[~st.session_state.df["ID"].isin(ids)].reset_index(drop=True)
            else:
                # fallback por comparação de linhas
                merged = pd.merge(st.session_state.df, sel_df, how="outer", indicator=True)
                st.session_state.df = merged[merged["_merge"]=="left_only"].drop(columns=["_merge"]).reset_index(drop=True)
            st.success("Linhas removidas.")
        else:
            st.warning("Nenhuma linha selecionada.")
with col_c:
    # Download como Excel
    excel_bytes = df_to_excel_bytes(ensure_columns(updated_df))
    st.download_button("⬇️ Baixar como Excel", data=excel_bytes, file_name="lancamentos_atualizados.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# Atualiza a sessão com os dados atuais (se usuário não clicou em salvar, damos opção)
st.session_state.df = ensure_columns(updated_df)

# -------------------------
# Gráficos e indicadores
# -------------------------
st.subheader("📈 Resumo e Gráficos")
df_graph = st.session_state.df.copy()

# Garante colunas numéricas
for col in ["Valor Total (R$)", "Valor Parcela (R$)"]:
    if col in df_graph.columns:
        df_graph[col] = pd.to_numeric(df_graph[col], errors="coerce").fillna(0.0)

# Prepara resumo mensal (considerando coluna 'Mês')
if "Mês" not in df_graph.columns or df_graph["Mês"].isnull().all():
    if "Data" in df_graph.columns:
        df_graph["Mês"] = df_graph["Data"].dt.strftime("%B").fillna("Sem mês")

resumo = df_graph.groupby(["Mês","Tipo (Receita/Despesa)"])["Valor Total (R$)"].sum().reset_index()
resumo_pivot = resumo.pivot(index="Mês", columns="Tipo (Receita/Despesa)", values="Valor Total (R$)").fillna(0)
# Ordena meses cronologicamente se possível
meses_ordem = ["janeiro","fevereiro","março","abril","maio","junho","julho","agosto","setembro","outubro","novembro","dezembro"]
# se os meses estão capitalizados com primeira letra maiuscula
resumo_pivot.index = [str(m).capitalize() for m in resumo_pivot.index]
# tenta ordenar conforme meses_ordem
try:
    resumo_pivot = resumo_pivot.reindex([m.capitalize() for m in meses_ordem])
except:
    pass
resumo_pivot = resumo_pivot.fillna(0)
resumo_pivot["Saldo Mensal"] = resumo_pivot.get("Receita", 0) - resumo_pivot.get("Despesa", 0)
resumo_pivot["Saldo Acumulado"] = resumo_pivot["Saldo Mensal"].cumsum()

# Exibe tabela resumida
st.dataframe(resumo_pivot.reset_index().rename(columns={"index":"Mês"}))

# Gráfico
if not resumo_pivot.empty:
    fig = px.line(resumo_pivot.reset_index(), x=resumo_pivot.reset_index()["index"], y=["Receita","Despesa","Saldo Acumulado"],
                  labels={"value":"R$","index":"Mês"}, markers=True)
    st.plotly_chart(fig, use_container_width=True)

# Indicadores gerais
total_receitas = df_graph.loc[df_graph["Tipo (Receita/Despesa)"]=="Receita", "Valor Total (R$)"].sum()
total_despesas = df_graph.loc[df_graph["Tipo (Receita/Despesa)"]=="Despesa", "Valor Total (R$)"].sum()
saldo_atual = total_receitas - total_despesas

st.markdown("### Indicadores")
col1, col2, col3 = st.columns(3)
col1.metric("Total Receitas (R$)", f"{total_receitas:,.2f}")
col2.metric("Total Despesas (R$)", f"{total_despesas:,.2f}")
col3.metric("Saldo Atual (R$)", f"{saldo_atual:,.2f}")

st.markdown("---")
st.caption("Observação: os dados são mantidos apenas na sessão do Streamlit por padrão. Para persistência por usuário é preciso integrar com banco (Supabase/Firebase/Google Sheets) ou implementar login.")
