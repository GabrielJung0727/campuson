-- CampusON 초기 DB 셋업
-- pgvector 확장 활성화 (RAG 벡터 검색용 - Day 8에서 사용)
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 타임존 설정
SET TIME ZONE 'Asia/Seoul';
