/**
 * @campuson/shared — 프론트엔드와 공유하는 타입/스키마 허브.
 *
 * v0.9: 단일 파일(~530줄) → 도메인별 분할. 각 도메인 파일에서 re-export.
 * 신규 DTO는 해당 도메인 파일에 추가하고 이곳은 재수출만 유지.
 */

export * from './enums';
export * from './auth';
export * from './questions';
export * from './diagnostic';
export * from './history';
export * from './ai';
export * from './kb';
