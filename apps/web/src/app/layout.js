"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.metadata = void 0;
exports.default = RootLayout;
require("./globals.css");
exports.metadata = {
    title: {
        default: 'CampusON',
        template: '%s | CampusON',
    },
    description: '경복대학교 보건계열 학생을 위한 AI 학습튜터링 플랫폼',
};
function RootLayout(_a) {
    var children = _a.children;
    return (<html lang="ko">
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased">{children}</body>
    </html>);
}
