#!/bin/bash
echo "JavaScript構文チェック開始..."
cd /home/ec2-user/AIChat/web

# 括弧のバランスチェック
open_braces=$(grep -o '{' index.html | wc -l)
close_braces=$(grep -o '}' index.html | wc -l)
open_parens=$(grep -o '(' index.html | wc -l)
close_parens=$(grep -o ')' index.html | wc -l)

echo "括弧バランス: { $open_braces } $close_braces, ( $open_parens ) $close_parens"

if [ $open_braces -ne $close_braces ]; then
    echo "❌ 波括弧のバランスが不正: { $open_braces ≠ } $close_braces"
    exit 1
fi

if [ $open_parens -ne $close_parens ]; then
    echo "❌ 丸括弧のバランスが不正: ( $open_parens ≠ ) $close_parens"
    exit 1
fi

echo "✅ JavaScript構文チェック完了"
