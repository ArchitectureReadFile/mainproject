"""
services/knowledge/mappers/__init__.py

RetrievedKnowledgeItem 매핑 책임을 source별로 모은 패키지.

각 mapper 모듈이 raw hit dict → RetrievedKnowledgeItem 변환을 전담한다.
새 source_type 추가 시 이 패키지에 mapper 파일 하나를 추가하면 된다.
retriever 내부에 _to_item 류 ad-hoc 함수를 두지 않는다.
"""
