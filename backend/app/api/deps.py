from __future__ import annotations

from fastapi import Request

from app.graph.neo4j_client import GraphRepository
from app.insights.graph_insights import GraphInsightEngine
from app.services.book_service import BookService
from app.services.chat_service import ChatService
from app.services.enterprise_service import EnterpriseService


def get_book_service(request: Request) -> BookService:
    return request.app.state.book_service


def get_graph_repo(request: Request) -> GraphRepository:
    return request.app.state.graph_repo


def get_insight_engine(request: Request) -> GraphInsightEngine:
    return request.app.state.insight_engine


def get_chat_service(request: Request) -> ChatService:
    return request.app.state.chat_service


def get_enterprise_service(request: Request) -> EnterpriseService:
    return request.app.state.enterprise_service
