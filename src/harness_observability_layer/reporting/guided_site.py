"""Static guided session reporting site."""

from __future__ import annotations

import json
from html import escape
from typing import Any, Dict, Iterable, List

from harness_observability_layer.observer.metrics import PRICING_PER_MILLION_TOKENS

from .guided_insights import (
    build_cost_efficiency_insights,
    build_overview_insights,
    build_qa_insights,
)


PAGES = [
    ("qa-report.html", "nav.qa"),
    ("cost-efficiency.html", "nav.cost"),
    ("workflow-trace.html", "nav.workflow"),
    ("raw-metrics.html", "nav.raw"),
    ("glossary.html", "nav.glossary"),
]


TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "eng": {
        "app.report_title": "Guided Session Report",
        "brand.eyebrow": "Harness Observability Layer",
        "hero.subtitle_fallback": "Operational view of session quality, cost, workflow trace, and raw attribution metrics.",
        "controls.language": "Language",
        "controls.theme": "Theme",
        "controls.eng": "ENG",
        "controls.pt": "PT",
        "controls.es": "ES",
        "controls.dark": "Dark",
        "controls.light": "Light",
        "nav.qa": "QA Report",
        "nav.cost": "Cost & Efficiency",
        "nav.workflow": "Workflow Trace",
        "nav.raw": "Raw Metrics",
        "nav.glossary": "Glossary",
        "artifact.summary": "summary.json",
        "artifact.metadata": "metadata.json",
        "artifact.normalized": "normalized.events.jsonl",
        "artifact.legacy": "legacy report",
        "hero.redirecting": "Redirecting to",
        "metrics.tokens": "Tokens",
        "metrics.cost": "Cost",
        "metrics.duration": "Duration",
        "metrics.failures": "Failures",
        "metrics.skills_loaded": "Skills Loaded",
        "metrics.skill_tools": "Skill-Attributed Tools",
        "metrics.skill_tokens": "Skill-Attributed Tokens",
        "metrics.unattributed_tokens": "Unattributed Tokens",
        "section.qa": "QA Report",
        "section.edited_without_read": "Edited Without Prior Read",
        "section.cost": "Cost & Efficiency",
        "section.token_profile": "Token Profile",
        "section.tokens_by_skill": "Tokens by Skill",
        "section.skill_token_breakdown": "Skill Token Breakdown",
        "section.workflow": "Workflow Trace",
        "section.skill_activity": "Skill Activity",
        "section.timeline": "Timeline",
        "section.top_tools": "Top Tools",
        "section.attribution_segments": "Attribution Segments",
        "section.top_files": "Top Files",
        "section.raw": "Raw Metrics",
        "section.attribution": "Attribution",
        "section.per_skill_aggregates": "Per-Skill Aggregates",
        "section.glossary": "Glossary",
        "section.boundary_types": "Boundary Types",
        "section.tool_calling_types": "Tool Calling Types",
        "support.raw_metrics": "Rendered from summary.json for direct auditability.",
        "support.attribution": "Deterministic attribution is derived from skill windows, user-message boundaries, and task/session completion events.",
        "support.workflow_source": "Normalized events source:",
        "support.glossary": "Plain-language explanations for the most abstract summary.json fields and workflow terms used across this session report.",
        "support.boundary_types": "These explain why an attribution segment was closed.",
        "support.tool_types": "These map the tool names counted in summary.json to what each tool does in practice.",
        "empty.qa": "No QA alerts were triggered for this session.",
        "empty.edited_without_read": "No edited-without-read files detected.",
        "empty.cost": "No cost or efficiency insights were triggered for this session.",
        "empty.workflow": "No overview insights were triggered for this session.",
        "empty.skill_activity": "No skill-attributed activity recorded.",
        "empty.timeline": "No normalized events available.",
        "empty.tools": "No tool activity recorded.",
        "empty.segments": "No attribution segments recorded.",
        "empty.files": "No file reads or edits recorded.",
        "empty.chart": "No attribution data available for charts.",
        "labels.unattributed": "Unattributed",
        "table.file": "File",
        "table.lines_read": "Lines Read",
        "table.edits": "Edits",
        "table.skill": "Skill",
        "table.segments": "Segments",
        "table.tool_calls": "Tool Calls",
        "table.total_tokens": "Total Tokens",
        "table.api_cost": "API Cost",
        "table.subscription": "Subscription",
        "table.driver": "Driver",
        "table.type": "Type",
        "table.tokens": "Tokens",
        "table.duration": "Duration",
        "table.boundary": "Boundary",
        "table.meaning": "Meaning",
        "table.example": "Example in This Session",
        "table.tool_type": "Tool Type",
        "index.title": "Imported Sessions",
        "index.subtitle": "Browse imported agent sessions for this project and open guided, session-specific reports with QA, cost, workflow, and raw metric views.",
        "index.indexed": "Sessions indexed",
        "index.session_description": "Session Description",
        "index.tools": "Tools",
        "index.top_tool": "Top Tool",
        "index.read": "Read",
        "index.edited": "Edited",
        "index.failure_rate": "Failure Rate",
        "index.empty": "No imported sessions found yet.",
        "glossary.skill_segment.title": "Skill Segment",
        "glossary.skill_segment.body": "A segment is a contiguous block of activity attributed to one driver, usually a skill such as brainstorming or writing-plans.",
        "glossary.skill_segment.detail1": "Stored in summary.json under attribution_segments.",
        "glossary.skill_segment.detail2": "Each segment records driver_name, driver_type, tool calls, token totals, duration, and boundary_reason.",
        "glossary.skill_segment.detail3": "Segments let the report separate work done under one skill from unattributed work between user messages and skill loads.",
        "glossary.boundary_types.title": "Boundary Types",
        "glossary.boundary_types.body": "Boundary types explain why one segment stopped and another one started or why the current one was closed.",
        "glossary.boundary_types.detail1": "These values appear as boundary_reason inside attribution_segments.",
        "glossary.boundary_types.detail2": "They are generated deterministically from skill loads, user messages, task completion, session completion, and end-of-stream handling.",
        "glossary.tool_types.title": "Tool Calling Types",
        "glossary.tool_types.body": "Tool calling types are the individual tool names counted in tool_calls_by_name, such as shell execution, patch application, or sub-agent control.",
        "glossary.tool_types.detail1": "Stored in summary.json under tool_calls_by_name.",
        "glossary.tool_types.detail2": "A single tool name groups repeated calls of the same capability across the session.",
        "glossary.tool_types.detail3": "Failures for the same tools appear separately in tool_failures_by_name.",
        "glossary.skill_attribution.title": "Skill Attribution",
        "glossary.skill_attribution.body": "Skill attribution aggregates all skill-driven segments by skill name so the report can show how much activity each loaded skill influenced.",
        "glossary.skill_attribution.detail1": "Stored in summary.json under skill_attribution.",
        "glossary.skill_attribution.detail2": "Each skill bucket includes segments_count, tool_call_count, token totals, file activity, and duration.",
        "observed.common": "Not observed in this summary; shown as a common example.",
        "observed.seen": "Observed {count} time(s) in this summary.",
        "plan.none": "N/A",
        "plan.included": "Included in {plan}",
    },
    "pt": {
        "app.report_title": "Relatorio Guiado de Sessao",
        "brand.eyebrow": "Harness Observability Layer",
        "hero.subtitle_fallback": "Visao operacional de qualidade da sessao, custo, fluxo de trabalho e metricas brutas de atribuicao.",
        "controls.language": "Idioma",
        "controls.theme": "Tema",
        "controls.eng": "ENG",
        "controls.pt": "PT",
        "controls.es": "ES",
        "controls.dark": "Escuro",
        "controls.light": "Claro",
        "nav.qa": "Relatorio QA",
        "nav.cost": "Custo e Eficiencia",
        "nav.workflow": "Fluxo de Trabalho",
        "nav.raw": "Metricas Brutas",
        "nav.glossary": "Glossario",
        "artifact.summary": "summary.json",
        "artifact.metadata": "metadata.json",
        "artifact.normalized": "normalized.events.jsonl",
        "artifact.legacy": "relatorio legado",
        "hero.redirecting": "Redirecionando para",
        "metrics.tokens": "Tokens",
        "metrics.cost": "Custo",
        "metrics.duration": "Duracao",
        "metrics.failures": "Falhas",
        "metrics.skills_loaded": "Skills Carregadas",
        "metrics.skill_tools": "Tools Atribuidas a Skills",
        "metrics.skill_tokens": "Tokens Atribuidos a Skills",
        "metrics.unattributed_tokens": "Tokens Nao Atribuidos",
        "section.qa": "Relatorio QA",
        "section.edited_without_read": "Editado Sem Leitura Previa",
        "section.cost": "Custo e Eficiencia",
        "section.token_profile": "Perfil de Tokens",
        "section.tokens_by_skill": "Tokens por Skill",
        "section.skill_token_breakdown": "Distribuicao de Tokens por Skill",
        "section.workflow": "Fluxo de Trabalho",
        "section.skill_activity": "Atividade por Skill",
        "section.timeline": "Linha do Tempo",
        "section.top_tools": "Principais Tools",
        "section.attribution_segments": "Segmentos de Atribuicao",
        "section.top_files": "Principais Arquivos",
        "section.raw": "Metricas Brutas",
        "section.attribution": "Atribuicao",
        "section.per_skill_aggregates": "Agregados por Skill",
        "section.glossary": "Glossario",
        "section.boundary_types": "Tipos de Boundary",
        "section.tool_calling_types": "Tipos de Tool Calling",
        "support.raw_metrics": "Renderizado a partir de summary.json para auditoria direta.",
        "support.attribution": "A atribuicao deterministica e derivada de janelas de skill, boundaries de mensagens do usuario e eventos de conclusao de tarefa ou sessao.",
        "support.workflow_source": "Fonte dos eventos normalizados:",
        "support.glossary": "Explicacoes em linguagem simples para os campos mais abstratos de summary.json e os termos de fluxo usados neste relatorio.",
        "support.boundary_types": "Isto explica por que um segmento de atribuicao foi encerrado.",
        "support.tool_types": "Isto mapeia os nomes de tool contados em summary.json para o que cada tool faz na pratica.",
        "empty.qa": "Nenhum alerta de QA foi acionado nesta sessao.",
        "empty.edited_without_read": "Nenhum arquivo editado sem leitura previa foi detectado.",
        "empty.cost": "Nenhum insight de custo ou eficiencia foi acionado nesta sessao.",
        "empty.workflow": "Nenhum insight geral foi acionado nesta sessao.",
        "empty.skill_activity": "Nenhuma atividade atribuida a skill foi registrada.",
        "empty.timeline": "Nenhum evento normalizado disponivel.",
        "empty.tools": "Nenhuma atividade de tool registrada.",
        "empty.segments": "Nenhum segmento de atribuicao registrado.",
        "empty.files": "Nenhuma leitura ou edicao de arquivo registrada.",
        "empty.chart": "Nenhum dado de atribuicao disponivel para o grafico.",
        "labels.unattributed": "Nao atribuido",
        "table.file": "Arquivo",
        "table.lines_read": "Linhas Lidas",
        "table.edits": "Edicoes",
        "table.skill": "Skill",
        "table.segments": "Segmentos",
        "table.tool_calls": "Chamadas de Tool",
        "table.total_tokens": "Tokens Totais",
        "table.api_cost": "Custo de API",
        "table.subscription": "Assinatura",
        "table.driver": "Driver",
        "table.type": "Tipo",
        "table.tokens": "Tokens",
        "table.duration": "Duracao",
        "table.boundary": "Boundary",
        "table.meaning": "Significado",
        "table.example": "Exemplo Nesta Sessao",
        "table.tool_type": "Tipo de Tool",
        "index.title": "Sessoes Importadas",
        "index.subtitle": "Navegue pelas sessoes importadas deste projeto e abra relatorios guiados por sessao com visoes de QA, custo, fluxo de trabalho e metricas brutas.",
        "index.indexed": "Sessoes indexadas",
        "index.session_description": "Descricao da Sessao",
        "index.tools": "Tools",
        "index.top_tool": "Tool Principal",
        "index.read": "Leitura",
        "index.edited": "Editado",
        "index.failure_rate": "Taxa de Falha",
        "index.empty": "Nenhuma sessao importada encontrada ainda.",
        "glossary.skill_segment.title": "Skill Segment",
        "glossary.skill_segment.body": "Um segmento e um bloco continuo de atividade atribuido a um driver, geralmente uma skill como brainstorming ou writing-plans.",
        "glossary.skill_segment.detail1": "Fica em summary.json no campo attribution_segments.",
        "glossary.skill_segment.detail2": "Cada segmento registra driver_name, driver_type, tool calls, totais de tokens, duracao e boundary_reason.",
        "glossary.skill_segment.detail3": "Os segmentos permitem separar o trabalho feito sob uma skill do trabalho nao atribuido entre mensagens do usuario e carregamentos de skill.",
        "glossary.boundary_types.title": "Tipos de Boundary",
        "glossary.boundary_types.body": "Os boundary types explicam por que um segmento terminou, outro comecou ou por que o segmento atual foi fechado.",
        "glossary.boundary_types.detail1": "Esses valores aparecem como boundary_reason dentro de attribution_segments.",
        "glossary.boundary_types.detail2": "Eles sao gerados de forma deterministica a partir de skill loads, mensagens do usuario, conclusao de tarefa, conclusao de sessao e fim do stream.",
        "glossary.tool_types.title": "Tipos de Tool Calling",
        "glossary.tool_types.body": "Os tipos de tool calling sao os nomes individuais contados em tool_calls_by_name, como execucao de shell, aplicacao de patch ou controle de subagentes.",
        "glossary.tool_types.detail1": "Ficam em summary.json no campo tool_calls_by_name.",
        "glossary.tool_types.detail2": "Um nome de tool agrupa chamadas repetidas da mesma capacidade ao longo da sessao.",
        "glossary.tool_types.detail3": "As falhas dessas mesmas tools aparecem separadamente em tool_failures_by_name.",
        "glossary.skill_attribution.title": "Skill Attribution",
        "glossary.skill_attribution.body": "Skill attribution agrega todos os segmentos dirigidos por skill pelo nome da skill para mostrar quanta atividade cada skill carregada influenciou.",
        "glossary.skill_attribution.detail1": "Fica em summary.json no campo skill_attribution.",
        "glossary.skill_attribution.detail2": "Cada bucket de skill inclui segments_count, tool_call_count, totais de tokens, atividade de arquivos e duracao.",
        "observed.common": "Nao observado neste summary; exibido como exemplo comum.",
        "observed.seen": "Observado {count} vez(es) neste summary.",
        "plan.none": "N/A",
        "plan.included": "Incluido no plano {plan}",
    },
    "es": {
        "app.report_title": "Reporte Guiado de Sesion",
        "brand.eyebrow": "Harness Observability Layer",
        "hero.subtitle_fallback": "Vista operativa de calidad de sesion, costo, flujo de trabajo y metricas brutas de atribucion.",
        "controls.language": "Idioma",
        "controls.theme": "Tema",
        "controls.eng": "ENG",
        "controls.pt": "PT",
        "controls.es": "ES",
        "controls.dark": "Oscuro",
        "controls.light": "Claro",
        "nav.qa": "Reporte QA",
        "nav.cost": "Costo y Eficiencia",
        "nav.workflow": "Flujo de Trabajo",
        "nav.raw": "Metricas Brutas",
        "nav.glossary": "Glosario",
        "artifact.summary": "summary.json",
        "artifact.metadata": "metadata.json",
        "artifact.normalized": "normalized.events.jsonl",
        "artifact.legacy": "reporte legado",
        "hero.redirecting": "Redirigiendo a",
        "metrics.tokens": "Tokens",
        "metrics.cost": "Costo",
        "metrics.duration": "Duracion",
        "metrics.failures": "Fallos",
        "metrics.skills_loaded": "Skills Cargadas",
        "metrics.skill_tools": "Tools Atribuidas a Skills",
        "metrics.skill_tokens": "Tokens Atribuidos a Skills",
        "metrics.unattributed_tokens": "Tokens No Atribuidos",
        "section.qa": "Reporte QA",
        "section.edited_without_read": "Editado Sin Lectura Previa",
        "section.cost": "Costo y Eficiencia",
        "section.token_profile": "Perfil de Tokens",
        "section.tokens_by_skill": "Tokens por Skill",
        "section.skill_token_breakdown": "Distribucion de Tokens por Skill",
        "section.workflow": "Flujo de Trabajo",
        "section.skill_activity": "Actividad por Skill",
        "section.timeline": "Linea de Tiempo",
        "section.top_tools": "Principales Tools",
        "section.attribution_segments": "Segmentos de Atribucion",
        "section.top_files": "Principales Archivos",
        "section.raw": "Metricas Brutas",
        "section.attribution": "Atribucion",
        "section.per_skill_aggregates": "Agregados por Skill",
        "section.glossary": "Glosario",
        "section.boundary_types": "Tipos de Boundary",
        "section.tool_calling_types": "Tipos de Tool Calling",
        "support.raw_metrics": "Renderizado desde summary.json para auditoria directa.",
        "support.attribution": "La atribucion deterministica se deriva de ventanas de skill, boundaries de mensajes del usuario y eventos de finalizacion de tarea o sesion.",
        "support.workflow_source": "Fuente de eventos normalizados:",
        "support.glossary": "Explicaciones en lenguaje claro para los campos mas abstractos de summary.json y los terminos de flujo usados en este reporte.",
        "support.boundary_types": "Esto explica por que un segmento de atribucion fue cerrado.",
        "support.tool_types": "Esto relaciona los nombres de tool contados en summary.json con lo que hace cada tool en la practica.",
        "empty.qa": "No se activaron alertas de QA en esta sesion.",
        "empty.edited_without_read": "No se detectaron archivos editados sin lectura previa.",
        "empty.cost": "No se activaron insights de costo o eficiencia en esta sesion.",
        "empty.workflow": "No se activaron insights generales en esta sesion.",
        "empty.skill_activity": "No se registro actividad atribuida a skills.",
        "empty.timeline": "No hay eventos normalizados disponibles.",
        "empty.tools": "No se registro actividad de tools.",
        "empty.segments": "No se registraron segmentos de atribucion.",
        "empty.files": "No se registraron lecturas o ediciones de archivos.",
        "empty.chart": "No hay datos de atribucion disponibles para el grafico.",
        "labels.unattributed": "No atribuido",
        "table.file": "Archivo",
        "table.lines_read": "Lineas Leidas",
        "table.edits": "Ediciones",
        "table.skill": "Skill",
        "table.segments": "Segmentos",
        "table.tool_calls": "Llamadas de Tool",
        "table.total_tokens": "Tokens Totales",
        "table.api_cost": "Costo de API",
        "table.subscription": "Suscripcion",
        "table.driver": "Driver",
        "table.type": "Tipo",
        "table.tokens": "Tokens",
        "table.duration": "Duracion",
        "table.boundary": "Boundary",
        "table.meaning": "Significado",
        "table.example": "Ejemplo en Esta Sesion",
        "table.tool_type": "Tipo de Tool",
        "index.title": "Sesiones Importadas",
        "index.subtitle": "Explora las sesiones importadas de este proyecto y abre reportes guiados por sesion con vistas de QA, costo, flujo de trabajo y metricas brutas.",
        "index.indexed": "Sesiones indexadas",
        "index.session_description": "Descripcion de la Sesion",
        "index.tools": "Tools",
        "index.top_tool": "Tool Principal",
        "index.read": "Lectura",
        "index.edited": "Editado",
        "index.failure_rate": "Tasa de Fallo",
        "index.empty": "Todavia no se encontraron sesiones importadas.",
        "glossary.skill_segment.title": "Skill Segment",
        "glossary.skill_segment.body": "Un segmento es un bloque continuo de actividad atribuido a un driver, normalmente una skill como brainstorming o writing-plans.",
        "glossary.skill_segment.detail1": "Se guarda en summary.json bajo attribution_segments.",
        "glossary.skill_segment.detail2": "Cada segmento registra driver_name, driver_type, tool calls, totales de tokens, duracion y boundary_reason.",
        "glossary.skill_segment.detail3": "Los segmentos permiten separar el trabajo realizado bajo una skill del trabajo no atribuido entre mensajes del usuario y cargas de skills.",
        "glossary.boundary_types.title": "Tipos de Boundary",
        "glossary.boundary_types.body": "Los boundary types explican por que un segmento termino, otro comenzo o por que el segmento actual fue cerrado.",
        "glossary.boundary_types.detail1": "Estos valores aparecen como boundary_reason dentro de attribution_segments.",
        "glossary.boundary_types.detail2": "Se generan de forma deterministica a partir de skill loads, mensajes del usuario, finalizacion de tarea, finalizacion de sesion y fin del stream.",
        "glossary.tool_types.title": "Tipos de Tool Calling",
        "glossary.tool_types.body": "Los tipos de tool calling son los nombres individuales contados en tool_calls_by_name, como ejecucion de shell, aplicacion de patch o control de subagentes.",
        "glossary.tool_types.detail1": "Se guardan en summary.json bajo tool_calls_by_name.",
        "glossary.tool_types.detail2": "Un nombre de tool agrupa llamadas repetidas de la misma capacidad durante la sesion.",
        "glossary.tool_types.detail3": "Los fallos de esas mismas tools aparecen por separado en tool_failures_by_name.",
        "glossary.skill_attribution.title": "Skill Attribution",
        "glossary.skill_attribution.body": "Skill attribution agrega todos los segmentos dirigidos por skills por nombre para mostrar cuanta actividad influyo cada skill cargada.",
        "glossary.skill_attribution.detail1": "Se guarda en summary.json bajo skill_attribution.",
        "glossary.skill_attribution.detail2": "Cada bucket de skill incluye segments_count, tool_call_count, totales de tokens, actividad de archivos y duracion.",
        "observed.common": "No observado en este summary; se muestra como ejemplo comun.",
        "observed.seen": "Observado {count} vez/veces en este summary.",
        "plan.none": "N/A",
        "plan.included": "Incluido en el plan {plan}",
    },
}


def _text(key: str) -> str:
    return TRANSLATIONS["eng"].get(key, key)


def _i18n_attrs(key: str, default: str | None = None) -> str:
    fallback = default if default is not None else _text(key)
    return (
        f' data-i18n="{escape(key, quote=True)}"'
        f' data-i18n-default="{escape(fallback, quote=True)}"'
    )


def _i18n_tag(tag: str, key: str, *, default: str | None = None, cls: str | None = None) -> str:
    class_attr = f' class="{escape(cls, quote=True)}"' if cls else ""
    return f"<{tag}{class_attr}{_i18n_attrs(key, default)}>{escape(default if default is not None else _text(key))}</{tag}>"


def _js_object_literal(value: Any) -> str:
    return (
        json.dumps(value, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


def _format_tokens(count: int) -> str:
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}K"
    return str(count)


def _format_duration(seconds: float) -> str:
    if seconds <= 0:
        return "—"
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.1f}m"
    return f"{minutes / 60:.1f}h"


def _format_cost(cost: Any) -> str:
    if cost is None:
        return "—"
    value = float(cost)
    if value < 0.01:
        return f"${value:.4f}"
    return f"${value:.2f}"


def _estimate_skill_cost(stats: Dict[str, Any], model: str | None) -> float | None:
    pricing = PRICING_PER_MILLION_TOKENS.get(model) if model else None
    if not pricing:
        return None
    input_cost = (
        int(stats.get("input_tokens", 0) or 0) / 1_000_000
    ) * pricing["input"]
    output_cost = (
        int(stats.get("output_tokens", 0) or 0) / 1_000_000
    ) * pricing["output"]
    cache_write_cost = (
        int(stats.get("cache_creation_input_tokens", 0) or 0) / 1_000_000
    ) * pricing["cache_write"]
    cache_read_cost = (
        int(stats.get("cache_read_tokens", 0) or 0) / 1_000_000
    ) * pricing["cache_read"]
    return input_cost + output_cost + cache_write_cost + cache_read_cost


def _subscription_label(plan_type: Any) -> str:
    if not plan_type:
        return _text("plan.none")
    return _text("plan.included").format(plan=str(plan_type).title())


def _nav(current_file: str) -> str:
    links = []
    for filename, label_key in PAGES:
        cls = "page-tab active" if filename == current_file else "page-tab"
        links.append(
            f'<a class="{cls}" href="./{filename}"{_i18n_attrs(label_key)}>{escape(_text(label_key))}</a>'
        )
    return "".join(links)


def _insight_cards(cards: Iterable[Dict[str, str]], empty_key: str) -> str:
    card_list = list(cards)
    if not card_list:
        return f'<div class="empty-state"{_i18n_attrs(empty_key)}>{escape(_text(empty_key))}</div>'
    return "".join(
        f"""
        <article class="insight-card">
          <h3>{escape(card["title"])}</h3>
          <p>{escape(card["interpretation"])}</p>
          <div class="evidence-line">{escape(card["evidence"])}</div>
        </article>
        """
        for card in card_list
    )


def _metric_row(summary: Dict[str, Any]) -> str:
    return f"""
    <section class="metric-row">
      <article class="metric-card">
        <div class="metric-label"{_i18n_attrs("metrics.tokens")}>{escape(_text("metrics.tokens"))}</div>
        <div class="metric-value">{escape(_format_tokens(int(summary.get("total_tokens", 0) or 0)))}</div>
      </article>
      <article class="metric-card">
        <div class="metric-label"{_i18n_attrs("metrics.cost")}>{escape(_text("metrics.cost"))}</div>
        <div class="metric-value">{escape(_format_cost(summary.get("estimated_cost_usd")))}</div>
      </article>
      <article class="metric-card">
        <div class="metric-label"{_i18n_attrs("metrics.duration")}>{escape(_text("metrics.duration"))}</div>
        <div class="metric-value">{escape(_format_duration(float(summary.get("session_duration_seconds", 0) or 0)))}</div>
      </article>
      <article class="metric-card">
        <div class="metric-label"{_i18n_attrs("metrics.failures")}>{escape(_text("metrics.failures"))}</div>
        <div class="metric-value">{escape(f"{float(summary.get('failure_rate_pct', 0) or 0):.1f}%")}</div>
      </article>
    </section>
    """


def _attribution_metric_row(summary: Dict[str, Any]) -> str:
    shares = summary.get("attribution_shares", {}) or {}
    unattributed = summary.get("unattributed_activity", {}) or {}
    return f"""
    <section class="metric-row metric-row-secondary">
      <article class="metric-card">
        <div class="metric-label"{_i18n_attrs("metrics.skills_loaded")}>{escape(_text("metrics.skills_loaded"))}</div>
        <div class="metric-value">{int(summary.get("distinct_skills_loaded", 0) or 0)}</div>
      </article>
      <article class="metric-card">
        <div class="metric-label"{_i18n_attrs("metrics.skill_tools")}>{escape(_text("metrics.skill_tools"))}</div>
        <div class="metric-value">{float(shares.get("skill_attributed_tool_call_pct", 0) or 0):.1f}%</div>
      </article>
      <article class="metric-card">
        <div class="metric-label"{_i18n_attrs("metrics.skill_tokens")}>{escape(_text("metrics.skill_tokens"))}</div>
        <div class="metric-value">{float(shares.get("skill_attributed_token_pct", 0) or 0):.1f}%</div>
      </article>
      <article class="metric-card">
        <div class="metric-label"{_i18n_attrs("metrics.unattributed_tokens")}>{escape(_text("metrics.unattributed_tokens"))}</div>
        <div class="metric-value">{escape(_format_tokens(int(unattributed.get("total_tokens", 0) or 0)))}</div>
      </article>
    </section>
    """


def _artifact_links(session_name: str) -> str:
    base = f"../../../sessions/{session_name}"
    return f"""
    <div class="artifact-links">
      <a href="{escape(base)}/summary.json"{_i18n_attrs("artifact.summary")}>{escape(_text("artifact.summary"))}</a>
      <a href="{escape(base)}/metadata.json"{_i18n_attrs("artifact.metadata")}>{escape(_text("artifact.metadata"))}</a>
      <a href="{escape(base)}/normalized.events.jsonl"{_i18n_attrs("artifact.normalized")}>{escape(_text("artifact.normalized"))}</a>
      <a href="{escape(base)}/report.html"{_i18n_attrs("artifact.legacy")}>{escape(_text("artifact.legacy"))}</a>
    </div>
    """


def _top_tools(summary: Dict[str, Any]) -> str:
    tools = summary.get("tool_calls_by_name", {}) or {}
    if not tools:
        return f'<div class="empty-state"{_i18n_attrs("empty.tools")}>{escape(_text("empty.tools"))}</div>'
    items = [
        f"<li><strong>{escape(str(name))}</strong><span>{int(count)}</span></li>"
        for name, count in sorted(tools.items(), key=lambda item: (-item[1], item[0]))[:8]
    ]
    return f'<ul class="mini-list">{"".join(items)}</ul>'


def _top_files(summary: Dict[str, Any]) -> str:
    files = summary.get("files", {}) or {}
    if not files:
        return f'<div class="empty-state"{_i18n_attrs("empty.files")}>{escape(_text("empty.files"))}</div>'
    items = []
    ordered = sorted(
        files.items(),
        key=lambda item: (
            -(item[1].get("union_lines_read") or 0),
            -(item[1].get("edit_count") or 0),
            item[0],
        ),
    )[:10]
    for path, meta in ordered:
        items.append(
            "<tr>"
            f"<td>{escape(path)}</td>"
            f"<td>{int(meta.get('union_lines_read', 0) or 0)}</td>"
            f"<td>{int(meta.get('edit_count', 0) or 0)}</td>"
            "</tr>"
        )
    return (
        '<table class="data-table"><thead><tr>'
        f'<th{_i18n_attrs("table.file")}>{escape(_text("table.file"))}</th>'
        f'<th{_i18n_attrs("table.lines_read")}>{escape(_text("table.lines_read"))}</th>'
        f'<th{_i18n_attrs("table.edits")}>{escape(_text("table.edits"))}</th>'
        '</tr></thead>'
        f"<tbody>{''.join(items)}</tbody></table>"
    )


def _skill_table(summary: Dict[str, Any]) -> str:
    return _skill_table_with_options(summary)


def _skill_table_with_options(
    summary: Dict[str, Any], *, include_cost_columns: bool = False
) -> str:
    skill_attribution = summary.get("skill_attribution", {}) or {}
    if not skill_attribution:
        return f'<div class="empty-state"{_i18n_attrs("empty.skill_activity")}>{escape(_text("empty.skill_activity"))}</div>'
    model = summary.get("model")
    subscription = _subscription_label(summary.get("plan_type"))
    rows = []
    for name, stats in sorted(
        skill_attribution.items(),
        key=lambda item: (
            -(item[1].get("total_tokens", 0) or 0),
            item[0],
        ),
    ):
        extra_columns = ""
        if include_cost_columns:
            extra_columns = (
                f"<td>{escape(_format_cost(_estimate_skill_cost(stats, model)))}</td>"
                f"<td>{escape(subscription)}</td>"
            )
        rows.append(
            "<tr>"
            f"<td>{escape(str(name))}</td>"
            f"<td>{int(stats.get('segments_count', 0) or 0)}</td>"
            f"<td>{int(stats.get('tool_call_count', 0) or 0)}</td>"
            f"<td>{escape(_format_tokens(int(stats.get('total_tokens', 0) or 0)))}</td>"
            f"{extra_columns}"
            "</tr>"
        )
    headers = (
        f'<th{_i18n_attrs("table.skill")}>{escape(_text("table.skill"))}</th>'
        f'<th{_i18n_attrs("table.segments")}>{escape(_text("table.segments"))}</th>'
        f'<th{_i18n_attrs("table.tool_calls")}>{escape(_text("table.tool_calls"))}</th>'
        f'<th{_i18n_attrs("table.total_tokens")}>{escape(_text("table.total_tokens"))}</th>'
    )
    if include_cost_columns:
        headers += (
            f'<th{_i18n_attrs("table.api_cost")}>{escape(_text("table.api_cost"))}</th>'
            f'<th{_i18n_attrs("table.subscription")}>{escape(_text("table.subscription"))}</th>'
        )
    return (
        f'<table class="data-table"><thead><tr>{headers}</tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _chart_data_attr(spec: Dict[str, Any]) -> str:
    return escape(json.dumps(spec, separators=(",", ":")), quote=True)


def _skill_token_chart(summary: Dict[str, Any]) -> str:
    skill_attribution = summary.get("skill_attribution", {}) or {}
    unattributed = summary.get("unattributed_activity", {}) or {}
    labels: List[str] = []
    totals: List[int] = []
    for name, stats in sorted(
        skill_attribution.items(),
        key=lambda item: (
            -(item[1].get("total_tokens", 0) or 0),
            item[0],
        ),
    ):
        labels.append(str(name))
        totals.append(int(stats.get("total_tokens", 0) or 0))
    if unattributed.get("total_tokens", 0):
        labels.append("Unattributed")
        totals.append(int(unattributed.get("total_tokens", 0) or 0))
    if not labels:
        return f'<div class="empty-state"{_i18n_attrs("empty.chart")}>{escape(_text("empty.chart"))}</div>'
    return (
        '<div id="skill-token-chart" class="chart-block" '
        f'data-chart="{_chart_data_attr({"labels": labels, "totals": totals, "display_totals": [_format_tokens(total) for total in totals]})}"></div>'
    )


def _segment_table(summary: Dict[str, Any]) -> str:
    segments = summary.get("attribution_segments", []) or []
    if not segments:
        return f'<div class="empty-state"{_i18n_attrs("empty.segments")}>{escape(_text("empty.segments"))}</div>'
    rows = []
    for segment in segments[:30]:
        rows.append(
            "<tr>"
            f"<td>{escape(str(segment.get('driver_name', '')))}</td>"
            f"<td>{escape(str(segment.get('driver_type', '')))}</td>"
            f"<td>{int(segment.get('tool_call_count', 0) or 0)}</td>"
            f"<td>{escape(_format_tokens(int(segment.get('total_tokens', 0) or 0)))}</td>"
            f"<td>{float(segment.get('duration_seconds', 0) or 0):.1f}s</td>"
            f"<td>{escape(str(segment.get('boundary_reason', '')))}</td>"
            "</tr>"
        )
    return (
        '<table class="data-table"><thead><tr>'
        f'<th{_i18n_attrs("table.driver")}>{escape(_text("table.driver"))}</th>'
        f'<th{_i18n_attrs("table.type")}>{escape(_text("table.type"))}</th>'
        f'<th{_i18n_attrs("table.tool_calls")}>{escape(_text("table.tool_calls"))}</th>'
        f'<th{_i18n_attrs("table.tokens")}>{escape(_text("table.tokens"))}</th>'
        f'<th{_i18n_attrs("table.duration")}>{escape(_text("table.duration"))}</th>'
        f'<th{_i18n_attrs("table.boundary")}>{escape(_text("table.boundary"))}</th>'
        '</tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _term_card(
    title_key: str, description_key: str, detail_keys: Iterable[str]
) -> str:
    items = "".join(
        f'<li{_i18n_attrs(detail_key)}>{escape(_text(detail_key))}</li>'
        for detail_key in detail_keys
    )
    return (
        '<article class="glossary-card">'
        + _i18n_tag("h3", title_key)
        + _i18n_tag("p", description_key)
        + (f'<ul class="bullet-list">{items}</ul>' if items else "")
        + "</article>"
    )


def _boundary_reason_description(reason: str) -> str:
    descriptions = {
        "next_skill_loaded": "The current segment closed because another skill was loaded and became the new active driver.",
        "user_message": "The segment ended when a new user message arrived, which starts a fresh unattributed window until another skill takes over.",
        "task_finished_boundary": "The segment was closed by a task completion event that also carries attributable activity.",
        "session_finished": "The segment ended when the session finished event closed any open work.",
        "session_finished_boundary": "The segment was closed by a session completion event that also carried attributable activity.",
        "end_of_stream": "The event stream ended while the segment was still open, so the report closed it at the end of the data.",
    }
    return descriptions.get(
        reason,
        "Boundary reason observed in the summary, but not yet documented in the glossary map.",
    )


def _tool_call_description(tool_name: str) -> str:
    descriptions = {
        "exec_command": "Runs a shell command in the workspace and records the execution as one tool call.",
        "write_stdin": "Sends more input to a command that is already running, often to drive an interactive session.",
        "apply_patch": "Applies a structured patch directly to files, typically for code edits without opening an editor.",
        "search_query": "Uses web search to fetch external information from the internet.",
        "open": "Opens a referenced web page or fetched resource for inspection.",
        "click": "Follows a link from an opened page during a browsing flow.",
        "find": "Finds matching text inside an opened page or document.",
        "image_query": "Searches for images related to a prompt.",
        "spawn_agent": "Starts a parallel sub-agent for a bounded task.",
        "send_input": "Sends more instructions to an existing sub-agent.",
        "wait_agent": "Waits for a sub-agent to finish or reach a terminal state.",
        "close_agent": "Stops a sub-agent that is no longer needed.",
        "update_plan": "Updates the visible execution plan for the current task.",
    }
    return descriptions.get(
        tool_name,
        "Tool type observed in the summary. This glossary can be extended with a tool-specific description later.",
    )


def _summary_json_glossary(summary: Dict[str, Any]) -> str:
    cards = [
        _term_card(
            "glossary.skill_segment.title",
            "glossary.skill_segment.body",
            [
                "glossary.skill_segment.detail1",
                "glossary.skill_segment.detail2",
                "glossary.skill_segment.detail3",
            ],
        ),
        _term_card(
            "glossary.boundary_types.title",
            "glossary.boundary_types.body",
            [
                "glossary.boundary_types.detail1",
                "glossary.boundary_types.detail2",
            ],
        ),
        _term_card(
            "glossary.tool_types.title",
            "glossary.tool_types.body",
            [
                "glossary.tool_types.detail1",
                "glossary.tool_types.detail2",
                "glossary.tool_types.detail3",
            ],
        ),
        _term_card(
            "glossary.skill_attribution.title",
            "glossary.skill_attribution.body",
            [
                "glossary.skill_attribution.detail1",
                "glossary.skill_attribution.detail2",
            ],
        ),
    ]
    return f'<div class="glossary-grid">{"".join(cards)}</div>'


def _boundary_reason_table(summary: Dict[str, Any]) -> str:
    segments = summary.get("attribution_segments", []) or []
    reasons = sorted(
        {
            str(segment.get("boundary_reason"))
            for segment in segments
            if segment.get("boundary_reason")
        }
    )
    if not reasons:
        reasons = ["next_skill_loaded", "user_message", "task_finished_boundary", "end_of_stream"]
    rows = []
    for reason in reasons:
        rows.append(
            "<tr>"
            f"<td><code>{escape(reason)}</code></td>"
            f"<td>{escape(_boundary_reason_description(reason))}</td>"
            "</tr>"
        )
    return (
        '<table class="data-table glossary-table"><thead><tr>'
        f'<th{_i18n_attrs("table.boundary")}>{escape(_text("table.boundary"))}</th>'
        f'<th{_i18n_attrs("table.meaning")}>{escape(_text("table.meaning"))}</th>'
        '</tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _tool_call_table(summary: Dict[str, Any]) -> str:
    tools = summary.get("tool_calls_by_name", {}) or {}
    names = sorted(str(name) for name in tools)
    if not names:
        names = ["exec_command", "apply_patch", "write_stdin"]
    rows = []
    for name in names:
        count = tools.get(name)
        observed = (
            _text("observed.seen").format(count=int(count))
            if count is not None
            else _text("observed.common")
        )
        rows.append(
            "<tr>"
            f"<td><code>{escape(name)}</code></td>"
            f"<td>{escape(_tool_call_description(name))}</td>"
            f"<td>{escape(observed)}</td>"
            "</tr>"
        )
    return (
        '<table class="data-table glossary-table"><thead><tr>'
        f'<th{_i18n_attrs("table.tool_type")}>{escape(_text("table.tool_type"))}</th>'
        f'<th{_i18n_attrs("table.meaning")}>{escape(_text("table.meaning"))}</th>'
        f'<th{_i18n_attrs("table.example")}>{escape(_text("table.example"))}</th>'
        '</tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _glossary_page(
    session_name: str, summary: Dict[str, Any], metadata: Dict[str, Any]
) -> str:
    title = str(metadata.get("display_title") or session_name)
    subtitle = str(metadata.get("display_subtitle") or session_name)
    body = (
        _metric_row(summary)
        + _attribution_metric_row(summary)
        + f'<section class="page-section">{_i18n_tag("h2", "section.glossary")}'
        + f'<p class="supporting-text"{_i18n_attrs("support.glossary")}>{escape(_text("support.glossary"))}</p>'
        + _summary_json_glossary(summary)
        + "</section>"
        + f'<section class="page-section">{_i18n_tag("h2", "section.boundary_types")}'
        + f'<p class="supporting-text"{_i18n_attrs("support.boundary_types")}>{escape(_text("support.boundary_types"))}</p>'
        + _boundary_reason_table(summary)
        + "</section>"
        + f'<section class="page-section">{_i18n_tag("h2", "section.tool_calling_types")}'
        + f'<p class="supporting-text"{_i18n_attrs("support.tool_types")}>{escape(_text("support.tool_types"))}</p>'
        + _tool_call_table(summary)
        + "</section>"
    )
    return _shell(
        session_name=session_name,
        title=title,
        subtitle=subtitle,
        current_file="glossary.html",
        body=body,
    )


def _chart_script() -> str:
    translations = _js_object_literal(TRANSLATIONS)
    return f"""
    <script data-hol="ui">
    (() => {{
      const messages = {translations};
      const localeKey = "hol:locale";
      const themeKey = "hol:theme";
      const root = document.documentElement;
      const defaultLocale = root.dataset.locale || "eng";
      const defaultTheme = root.dataset.theme || "dark";

      const getMessages = (locale) => messages[locale] || messages.eng || {{}};
      const t = (locale, key) => getMessages(locale)[key] || (messages.eng || {{}})[key] || key;

      const applyLocale = (locale) => {{
        root.dataset.locale = locale;
        root.lang = locale === "pt" ? "pt-BR" : locale === "es" ? "es" : "en";
        document.querySelectorAll("[data-i18n]").forEach((node) => {{
          const key = node.dataset.i18n;
          const value = t(locale, key);
          node.textContent = value;
        }});
        document.querySelectorAll("[data-locale-option]").forEach((node) => {{
          node.classList.toggle("is-active", node.dataset.localeOption === locale);
        }});
        document.querySelectorAll("[data-chart]").forEach((node) => {{
          const spec = JSON.parse(node.dataset.chart);
          const totals = spec.totals || [];
          const displayTotals = spec.display_totals || totals;
          const labels = (spec.labels || []).map((label) =>
            label === "Unattributed" ? t(locale, "labels.unattributed") : label
          );
          const max = Math.max(...totals, 1);
          node.innerHTML = labels.map((label, i) =>
            `<div class="chart-row"><span class="chart-label">${{label}}</span><div class="chart-bar"><span style="width:${{(totals[i] / max) * 100}}%"></span></div><strong>${{displayTotals[i]}}</strong></div>`
          ).join("");
        }});
        localStorage.setItem(localeKey, locale);
      }};

      const applyTheme = (theme) => {{
        root.dataset.theme = theme;
        document.querySelectorAll("[data-theme-option]").forEach((node) => {{
          node.classList.toggle("is-active", node.dataset.themeOption === theme);
        }});
        localStorage.setItem(themeKey, theme);
      }};

      const savedLocale = localStorage.getItem("hol:locale") || defaultLocale;
      const savedTheme = localStorage.getItem("hol:theme") || defaultTheme;
      applyTheme(savedTheme);
      applyLocale(savedLocale);

      document.querySelectorAll("[data-locale-option]").forEach((node) => {{
        node.addEventListener("click", () => applyLocale(node.dataset.localeOption));
      }});
      document.querySelectorAll("[data-theme-option]").forEach((node) => {{
        node.addEventListener("click", () => applyTheme(node.dataset.themeOption));
      }});
    }})();
    </script>
    """


def _timeline(events: List[Dict[str, Any]]) -> str:
    if not events:
        return f'<div class="empty-state"{_i18n_attrs("empty.timeline")}>{escape(_text("empty.timeline"))}</div>'
    items = []
    for event in events[:20]:
        items.append(
            f"<li><strong>{escape(str(event.get('event_type', 'unknown')))}</strong>"
            f"<span>{escape(str(event.get('ts', '')))}</span></li>"
        )
    return f'<ul class="mini-list timeline-list">{"".join(items)}</ul>'


def _shell(
    *,
    session_name: str,
    title: str,
    subtitle: str,
    current_file: str,
    body: str,
    include_chart_script: bool = False,
) -> str:
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark" data-locale="eng">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(title)} · {_text("app.report_title")}</title>
  <link rel="stylesheet" href="./report.css" />
</head>
  <body>
  <main class="page-shell">
    <section class="hero">
      <div class="hero-topbar">
        <div class="hero-heading">
          <p class="eyebrow"{_i18n_attrs("brand.eyebrow")}>{escape(_text("brand.eyebrow"))}</p>
          <h1>{escape(title)}</h1>
          <p class="hero-text">{escape(subtitle)}</p>
        </div>
        <div class="hero-controls">
          <div class="control-group" data-locale-switcher>
            <span class="control-label"{_i18n_attrs("controls.language")}>{escape(_text("controls.language"))}</span>
            <button type="button" class="control-chip" data-locale-option="eng">{escape(_text("controls.eng"))}</button>
            <button type="button" class="control-chip" data-locale-option="pt">{escape(_text("controls.pt"))}</button>
            <button type="button" class="control-chip" data-locale-option="es">{escape(_text("controls.es"))}</button>
          </div>
          <div class="control-group" data-theme-switcher>
            <span class="control-label"{_i18n_attrs("controls.theme")}>{escape(_text("controls.theme"))}</span>
            <button type="button" class="control-chip" data-theme-option="dark">{escape(_text("controls.dark"))}</button>
            <button type="button" class="control-chip" data-theme-option="light">{escape(_text("controls.light"))}</button>
          </div>
        </div>
      </div>
      <nav class="page-tabs">{_nav(current_file)}</nav>
      {_artifact_links(session_name)}
    </section>
    {body}
  </main>
  {_chart_script()}
</body>
</html>"""


def _redirect_page(
    *, session_name: str, title: str, subtitle: str, target_file: str
) -> str:
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark" data-locale="eng">
<head>
  <meta charset="utf-8" />
  <meta http-equiv="refresh" content="0; url=./{escape(target_file)}" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(title)} · {_text("app.report_title")}</title>
  <link rel="stylesheet" href="./report.css" />
</head>
<body>
  <main class="page-shell">
    <section class="hero">
      <p class="eyebrow"{_i18n_attrs("brand.eyebrow")}>{escape(_text("brand.eyebrow"))}</p>
      <h1>{escape(title)}</h1>
      <p class="hero-text">{escape(subtitle)}</p>
      <p class="supporting-text"><span{_i18n_attrs("hero.redirecting")}>{escape(_text("hero.redirecting"))}</span> <a href="./{escape(target_file)}">{escape(target_file)}</a>…</p>
      {_artifact_links(session_name)}
    </section>
  </main>
  {_chart_script()}
</body>
</html>"""


def _qa_page(session_name: str, summary: Dict[str, Any], metadata: Dict[str, Any]) -> str:
    title = str(metadata.get("display_title") or session_name)
    subtitle = str(metadata.get("display_subtitle") or session_name)
    edited_without_read = summary.get("edited_without_prior_read", []) or []
    body = (
        _metric_row(summary)
        + _attribution_metric_row(summary)
        + f'<section class="page-section">{_i18n_tag("h2", "section.qa")}<div class="insight-grid">'
        + _insight_cards(
            build_qa_insights(summary),
            "empty.qa",
        )
        + "</div></section>"
        + f'<section class="page-section">{_i18n_tag("h2", "section.edited_without_read")}'
        + (
            '<ul class="bullet-list">'
            + "".join(f"<li>{escape(str(path))}</li>" for path in edited_without_read)
            + "</ul>"
            if edited_without_read
            else f'<div class="empty-state"{_i18n_attrs("empty.edited_without_read")}>{escape(_text("empty.edited_without_read"))}</div>'
        )
        + "</section>"
    )
    return _shell(
        session_name=session_name,
        title=title,
        subtitle=subtitle,
        current_file="qa-report.html",
        body=body,
    )


def _cost_page(
    session_name: str, summary: Dict[str, Any], metadata: Dict[str, Any]
) -> str:
    title = str(metadata.get("display_title") or session_name)
    subtitle = str(metadata.get("display_subtitle") or session_name)
    token_breakdown = (
        f"{_format_tokens(int(summary.get('total_input_tokens', 0) or 0))} in / "
        f"{_format_tokens(int(summary.get('total_cache_read_tokens', 0) or 0))} cache / "
        f"{_format_tokens(int(summary.get('total_output_tokens', 0) or 0))} out"
    )
    body = (
        _metric_row(summary)
        + _attribution_metric_row(summary)
        + f'<section class="page-section">{_i18n_tag("h2", "section.cost")}<div class="insight-grid">'
        + _insight_cards(
            build_cost_efficiency_insights(summary),
            "empty.cost",
        )
        + "</div></section>"
        + f'<section class="page-section">{_i18n_tag("h2", "section.token_profile")}<p class="supporting-text">{escape(token_breakdown)}</p></section>'
        + f'<section class="page-section">{_i18n_tag("h2", "section.tokens_by_skill")}'
        + _skill_table_with_options(summary, include_cost_columns=True)
        + f'<div class="chart-section">{_i18n_tag("h3", "section.skill_token_breakdown")}'
        + _skill_token_chart(summary)
        + "</section>"
    )
    return _shell(
        session_name=session_name,
        title=title,
        subtitle=subtitle,
        current_file="cost-efficiency.html",
        body=body,
        include_chart_script=True,
    )


def _workflow_page(
    session_name: str,
    summary: Dict[str, Any],
    metadata: Dict[str, Any],
    normalized_events_file: str,
    events: List[Dict[str, Any]],
) -> str:
    title = str(metadata.get("display_title") or session_name)
    subtitle = str(metadata.get("display_subtitle") or session_name)
    body = (
        _metric_row(summary)
        + _attribution_metric_row(summary)
        + f'<section class="page-section">{_i18n_tag("h2", "section.workflow")}<div class="insight-grid">'
        + _insight_cards(
            build_overview_insights(summary),
            "empty.workflow",
        )
        + "</div>"
        + f'<p class="supporting-text"><span{_i18n_attrs("support.workflow_source")}>{escape(_text("support.workflow_source"))}</span> {escape(normalized_events_file)}</p>'
        + "</section>"
        + f'<section class="page-section">{_i18n_tag("h2", "section.skill_activity")}'
        + _skill_table(summary)
        + "</section>"
        + f'<section class="page-section split-section"><div>{_i18n_tag("h2", "section.timeline")}'
        + _timeline(events)
        + f'</div><div>{_i18n_tag("h2", "section.top_tools")}'
        + _top_tools(summary)
        + "</div></section>"
        + f'<section class="page-section">{_i18n_tag("h2", "section.attribution_segments")}'
        + _segment_table(summary)
        + "</section>"
        + f'<section class="page-section">{_i18n_tag("h2", "section.top_files")}'
        + _top_files(summary)
        + "</section>"
    )
    return _shell(
        session_name=session_name,
        title=title,
        subtitle=subtitle,
        current_file="workflow-trace.html",
        body=body,
    )


def _raw_page(session_name: str, summary: Dict[str, Any], metadata: Dict[str, Any]) -> str:
    title = str(metadata.get("display_title") or session_name)
    subtitle = str(metadata.get("display_subtitle") or session_name)
    summary_json = escape(json.dumps(summary, indent=2))
    body = (
        _metric_row(summary)
        + f'<section class="page-section">{_i18n_tag("h2", "section.raw")}'
        + f'<p class="supporting-text"{_i18n_attrs("support.raw_metrics")}>{escape(_text("support.raw_metrics"))}</p>'
        + f'<pre class="json-block">{summary_json}</pre>'
        + "</section>"
        + f'<section class="page-section">{_i18n_tag("h2", "section.attribution")}'
        + f'<p class="supporting-text"{_i18n_attrs("support.attribution")}>{escape(_text("support.attribution"))}</p>'
        + _i18n_tag("h3", "section.per_skill_aggregates")
        + _skill_table(summary)
        + _i18n_tag("h3", "section.attribution_segments")
        + _segment_table(summary)
        + "</section>"
    )
    return _shell(
        session_name=session_name,
        title=title,
        subtitle=subtitle,
        current_file="raw-metrics.html",
        body=body,
    )


def report_css() -> str:
    return """
:root {
  --bg: #0b0f14;
  --bg-elevated: #11161d;
  --surface: #141b22;
  --surface-2: #19212b;
  --line: rgba(157, 176, 201, 0.18);
  --line-strong: rgba(157, 176, 201, 0.32);
  --ink: #edf3ff;
  --muted: #94a3b8;
  --accent: #f97316;
  --accent-soft: rgba(249, 115, 22, 0.16);
  --accent-blue: #38bdf8;
  --accent-green: #84cc16;
  --shadow: 0 24px 70px rgba(0, 0, 0, 0.35);
  --chip-bg: #0f141b;
  --chip-active: linear-gradient(135deg, rgba(56, 189, 248, 0.22), rgba(249, 115, 22, 0.2));
}
[data-theme="light"] {
  --bg: #eef3f8;
  --bg-elevated: #f8fbff;
  --surface: #ffffff;
  --surface-2: #f4f8fc;
  --line: rgba(15, 23, 42, 0.1);
  --line-strong: rgba(15, 23, 42, 0.18);
  --ink: #0f172a;
  --muted: #475569;
  --accent: #ea580c;
  --accent-soft: rgba(234, 88, 12, 0.12);
  --accent-blue: #0284c7;
  --accent-green: #4d7c0f;
  --shadow: 0 22px 50px rgba(15, 23, 42, 0.08);
  --chip-bg: #eef4f9;
  --chip-active: linear-gradient(135deg, rgba(2, 132, 199, 0.14), rgba(234, 88, 12, 0.12));
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "IBM Plex Sans", "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  color: var(--ink);
  background:
    radial-gradient(circle at top left, rgba(56, 189, 248, 0.12), transparent 24%),
    radial-gradient(circle at top right, rgba(249, 115, 22, 0.12), transparent 22%),
    linear-gradient(180deg, var(--bg), var(--bg-elevated));
}
.page-shell {
  width: min(1560px, calc(100vw - 40px));
  margin: 0 auto;
  padding: 18px 0 34px;
}
.hero, .metric-card, .page-section, .insight-card {
  background: var(--surface);
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
}
.glossary-card {
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 18px;
}
.hero, .page-section { border-radius: 14px; padding: 18px; margin-bottom: 14px; }
.hero {
  background:
    linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0)),
    var(--surface);
}
.hero-topbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
.hero-heading { min-width: 0; }
.hero-controls {
  display: grid;
  grid-template-columns: repeat(2, max-content);
  gap: 10px;
}
.control-group {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 10px;
  background: var(--chip-bg);
  border: 1px solid var(--line);
}
.control-label {
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--muted);
}
.control-chip {
  appearance: none;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--muted);
  border-radius: 999px;
  padding: 7px 10px;
  font: inherit;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}
.control-chip.is-active {
  color: var(--ink);
  border-color: var(--line-strong);
  background: var(--chip-active);
  box-shadow: inset 0 0 0 1px rgba(255,255,255,0.05);
}
.eyebrow { margin: 0 0 8px; font-size: 11px; letter-spacing: 0.22em; text-transform: uppercase; color: var(--accent-blue); }
h1, h2, h3, p { margin: 0; }
h1 { font-size: clamp(28px, 4vw, 48px); line-height: 0.98; overflow-wrap: anywhere; }
h2 { font-size: 17px; letter-spacing: 0.01em; margin-bottom: 14px; }
h3 { font-size: 14px; color: var(--ink); }
.hero-text, .supporting-text, .evidence-line, .empty-state { color: var(--muted); }
.hero-text {
  margin-top: 10px;
  line-height: 1.5;
  max-width: 72ch;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.page-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid var(--line);
}
.page-tab {
  text-decoration: none;
  color: var(--muted);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 9px 12px;
  background: var(--chip-bg);
  font-size: 13px;
  font-weight: 700;
}
.page-tab.active {
  color: var(--ink);
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.16), rgba(249, 115, 22, 0.16));
  border-color: var(--line-strong);
}
.artifact-links {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 14px;
}
.artifact-links a {
  color: var(--accent-blue);
  text-decoration: none;
  font-size: 12px;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: var(--chip-bg);
}
.metric-row { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; margin-bottom: 18px; }
.metric-row-secondary { margin-top: -4px; }
.metric-card {
  border-radius: 12px;
  padding: 16px;
  position: relative;
  overflow: hidden;
}
.metric-card::before {
  content: "";
  position: absolute;
  inset: 0 auto auto 0;
  width: 100%;
  height: 2px;
  background: linear-gradient(90deg, var(--accent-blue), var(--accent), var(--accent-green));
  opacity: 0.75;
}
.metric-label { font-size: 12px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted); }
.metric-value { margin-top: 8px; font-size: clamp(24px, 4vw, 40px); font-weight: 700; line-height: 1; }
.insight-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }
.glossary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; margin-top: 16px; }
.insight-card { border-radius: 12px; padding: 18px; background: var(--surface-2); }
.glossary-card p { margin-top: 8px; line-height: 1.45; }
.insight-card p { margin-top: 8px; line-height: 1.45; }
.evidence-line { margin-top: 10px; font-size: 13px; }
.mini-list, .bullet-list { margin: 0; padding-left: 18px; }
.mini-list li, .bullet-list li { margin: 6px 0; }
.mini-list li span { color: var(--muted); margin-left: 8px; }
.split-section { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
.hero-panel {
  min-width: 140px;
  padding: 16px 18px;
  border-radius: 12px;
  border: 1px solid var(--line);
  background: var(--surface-2);
  display: grid;
  gap: 6px;
  align-content: start;
  width: fit-content;
  justify-self: start;
}
.artifact-label {
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--muted);
}
.hero-panel code {
  font-family: "IBM Plex Mono", "SFMono-Regular", Consolas, monospace;
  font-size: clamp(26px, 4vw, 40px);
  color: var(--ink);
}
.session-grid {
  padding: 0;
  overflow: hidden;
}
.session-grid-head,
.session-row {
  display: grid;
  grid-template-columns: minmax(320px, 3fr) 90px minmax(120px, 1.2fr) 70px 80px 110px 120px 110px 120px;
  gap: 0;
}
.session-grid-head {
  background: var(--surface-2);
  border-bottom: 1px solid var(--line);
}
.session-grid-head > div {
  padding: 14px 12px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 11px;
  font-weight: 700;
}
.session-grid-body {
  display: grid;
}
.session-row {
  text-decoration: none;
  color: inherit;
  border-bottom: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.01);
}
.session-row:hover {
  background: linear-gradient(90deg, rgba(56, 189, 248, 0.08), rgba(249, 115, 22, 0.08));
}
.session-row-main,
.session-row-metric {
  padding: 14px 12px;
}
.session-row-main {
  display: grid;
  gap: 6px;
}
.session-row-kicker {
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--accent-blue);
}
.session-row-title {
  font-size: 18px;
  font-weight: 700;
  line-height: 1.1;
}
.session-row-subtitle,
.session-row-context {
  color: var(--muted);
  font-size: 13px;
  line-height: 1.45;
}
.session-row-context {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.session-row-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.session-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  border: 1px solid var(--line);
  padding: 5px 8px;
  font-size: 11px;
  color: var(--muted);
  background: var(--chip-bg);
}
.session-badge.source {
  color: var(--accent-blue);
}
.session-badge.warning {
  color: #fbbf24;
  border-color: rgba(251, 191, 36, 0.32);
}
.session-row-metric {
  display: grid;
  align-content: center;
  justify-items: start;
  font-weight: 700;
  border-left: 1px solid var(--line);
}
.session-row-metric-text {
  font-weight: 500;
  color: var(--muted);
}
.session-row-metric-stack strong {
  font-size: 18px;
}
.session-row-metric-stack span {
  color: var(--muted);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.data-table th, .data-table td { text-align: left; padding: 11px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }
.data-table th {
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 11px;
  font-weight: 700;
}
.chart-section { margin-top: 20px; }
.chart-block { display: grid; gap: 10px; margin-top: 12px; }
.chart-row { display: grid; grid-template-columns: minmax(100px, 180px) 1fr auto; gap: 12px; align-items: center; }
.chart-label { overflow-wrap: anywhere; }
.chart-bar { height: 10px; border-radius: 999px; background: rgba(148, 163, 184, 0.14); overflow: hidden; }
.chart-bar span { display: block; height: 100%; background: linear-gradient(90deg, var(--accent-blue), var(--accent)); border-radius: 999px; }
.json-block {
  margin: 0;
  padding: 18px;
  border-radius: 12px;
  background: #0a0f15;
  color: #dbeafe;
  border: 1px solid rgba(56, 189, 248, 0.12);
  overflow: auto;
  max-height: 480px;
}
@media (max-width: 980px) {
  .page-shell { width: calc(100vw - 20px); }
  .hero-topbar, .metric-row, .split-section { grid-template-columns: 1fr; display: grid; }
  .hero-controls { grid-template-columns: 1fr; }
  .session-grid-head { display: none; }
  .session-row {
    grid-template-columns: 1fr 1fr;
  }
  .session-row-main {
    grid-column: 1 / -1;
    border-bottom: 1px solid var(--line);
  }
  .session-row-metric {
    border-left: none;
    border-top: 1px solid var(--line);
  }
}
"""


def build_guided_session_site(
    *,
    session_name: str,
    summary: Dict[str, Any],
    metadata: Dict[str, Any],
    normalized_events_file: str,
    events: List[Dict[str, Any]],
) -> Dict[str, str]:
    title = str(metadata.get("display_title") or session_name)
    subtitle = str(metadata.get("display_subtitle") or session_name)
    return {
        "index.html": _redirect_page(
            session_name=session_name,
            title=title,
            subtitle=subtitle,
            target_file="workflow-trace.html",
        ),
        "qa-report.html": _qa_page(session_name, summary, metadata),
        "cost-efficiency.html": _cost_page(session_name, summary, metadata),
        "workflow-trace.html": _workflow_page(
            session_name, summary, metadata, normalized_events_file, events
        ),
        "raw-metrics.html": _raw_page(session_name, summary, metadata),
        "glossary.html": _glossary_page(session_name, summary, metadata),
        "report.css": report_css(),
    }
