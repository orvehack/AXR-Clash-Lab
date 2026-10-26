package com.axr.calculator;

import android.app.Activity;
import android.os.Bundle;
import android.graphics.Color;
import android.graphics.Typeface;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.GridLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.math.BigDecimal;
import java.math.MathContext;
import java.math.RoundingMode;

/**
 * AXR Calculadora: a self-contained calculator implemented from scratch.
 * No network access, third-party libraries, or copied project assets are used.
 */
public class MainActivity extends Activity {
    private static final int BG = Color.rgb(16, 21, 29);
    private static final int PANEL = Color.rgb(25, 33, 44);
    private static final int KEY = Color.rgb(38, 48, 62);
    private static final int ACCENT = Color.rgb(88, 214, 160);
    private static final int TEXT = Color.rgb(245, 248, 252);
    private static final int MUTED = Color.rgb(153, 166, 184);

    private TextView expressionView;
    private TextView resultView;
    private String expression = "";
    private boolean justEvaluated = false;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        buildInterface();
    }

    private void buildInterface() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(20), dp(18), dp(20), dp(18));
        root.setBackgroundColor(BG);

        TextView brand = new TextView(this);
        brand.setText("AXR  /  CALCULADORA");
        brand.setTextColor(ACCENT);
        brand.setTextSize(13);
        brand.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        brand.setLetterSpacing(0.08f);
        root.addView(brand, new LinearLayout.LayoutParams(-1, dp(34)));

        LinearLayout display = new LinearLayout(this);
        display.setOrientation(LinearLayout.VERTICAL);
        display.setGravity(Gravity.BOTTOM | Gravity.END);
        display.setPadding(dp(16), dp(18), dp(16), dp(18));
        display.setBackgroundColor(PANEL);

        expressionView = new TextView(this);
        expressionView.setTextColor(MUTED);
        expressionView.setTextSize(18);
        expressionView.setGravity(Gravity.END);
        expressionView.setSingleLine(true);
        display.addView(expressionView, new LinearLayout.LayoutParams(-1, dp(38)));

        resultView = new TextView(this);
        resultView.setText("0");
        resultView.setTextColor(TEXT);
        resultView.setTextSize(42);
        resultView.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        resultView.setGravity(Gravity.END | Gravity.CENTER_VERTICAL);
        resultView.setSingleLine(true);
        display.addView(resultView, new LinearLayout.LayoutParams(-1, dp(68)));

        LinearLayout.LayoutParams displayParams = new LinearLayout.LayoutParams(-1, 0, 1.05f);
        displayParams.bottomMargin = dp(18);
        root.addView(display, displayParams);

        String[][] keys = {
            {"AC", "DEL", "%", "÷"},
            {"7", "8", "9", "×"},
            {"4", "5", "6", "−"},
            {"1", "2", "3", "+"},
            {"±", "0", ".", "="}
        };
        GridLayout grid = new GridLayout(this);
        grid.setColumnCount(4);
        grid.setRowCount(5);
        grid.setUseDefaultMargins(false);

        for (int r = 0; r < keys.length; r++) {
            for (int c = 0; c < keys[r].length; c++) {
                final String key = keys[r][c];
                Button button = new Button(this);
                button.setText(key);
                button.setAllCaps(false);
                button.setTextSize(key.length() > 2 ? 16 : 22);
                button.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
                button.setTextColor((isOperator(key) || key.equals("=")) ? BG : TEXT);
                button.setBackgroundTintList(android.content.res.ColorStateList.valueOf(
                    (key.equals("=") ? ACCENT : isOperator(key) || key.equals("AC") ? ACCENT : KEY)));
                button.setPadding(0, 0, 0, 0);
                button.setOnClickListener(v -> onKey(key));
                GridLayout.LayoutParams p = new GridLayout.LayoutParams(
                    GridLayout.spec(r, 1, 1f), GridLayout.spec(c, 1, 1f));
                p.width = 0;
                p.height = 0;
                p.setMargins(dp(4), dp(4), dp(4), dp(4));
                grid.addView(button, p);
            }
        }
        root.addView(grid, new LinearLayout.LayoutParams(-1, 0, 2.2f));

        TextView footer = new TextView(this);
        footer.setText("Simple • Privada • Sin internet");
        footer.setTextColor(MUTED);
        footer.setTextSize(12);
        footer.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams fp = new LinearLayout.LayoutParams(-1, dp(30));
        fp.topMargin = dp(6);
        root.addView(footer, fp);

        setContentView(root);
    }

    private void onKey(String key) {
        if (key.equals("AC")) {
            expression = "";
            justEvaluated = false;
            show("0", "");
            return;
        }
        if (key.equals("DEL")) {
            if (justEvaluated) expression = resultView.getText().toString();
            if (!expression.isEmpty()) expression = expression.substring(0, expression.length() - 1);
            justEvaluated = false;
            show(expression.isEmpty() ? "0" : expression, "");
            return;
        }
        if (key.equals("=")) {
            calculate();
            return;
        }
        if (key.equals("±")) {
            toggleSign();
            return;
        }
        if (key.equals("%")) {
            applyPercent();
            return;
        }
        if (justEvaluated && !isOperator(key)) expression = "";
        justEvaluated = false;
        if (isOperator(key)) {
            if (expression.isEmpty()) {
                if (key.equals("−")) expression = "−";
                else return;
            } else if (endsWithOperator()) {
                expression = expression.substring(0, expression.length() - 1) + key;
            } else {
                expression += key;
            }
        } else if (key.equals(".")) {
            int start = lastNumberStart();
            String tail = expression.substring(start);
            if (tail.contains(".")) return;
            if (tail.isEmpty() || tail.equals("−")) expression += "0";
            expression += ".";
        } else {
            expression += key;
        }
        show(expression.isEmpty() ? "0" : expression, "");
    }

    private void calculate() {
        if (expression.isEmpty() || endsWithOperator()) return;
        try {
            BigDecimal value = new Parser(expression).parse();
            String formatted = value.stripTrailingZeros().toPlainString();
            if (formatted.equals("-0")) formatted = "0";
            String old = expression;
            expression = formatted;
            justEvaluated = true;
            show(formatted, old + " =");
        } catch (ArithmeticException | IllegalArgumentException ex) {
            show("Error", expression);
            expression = "";
            justEvaluated = true;
        }
    }

    private void applyPercent() {
        if (expression.isEmpty() || endsWithOperator()) return;
        int start = lastNumberStart();
        try {
            BigDecimal n = new BigDecimal(expression.substring(start).replace('−', '-'));
            String percent = n.divide(BigDecimal.valueOf(100), MathContext.DECIMAL64).stripTrailingZeros().toPlainString();
            expression = expression.substring(0, start) + percent;
            show(expression, "");
        } catch (NumberFormatException ignored) { }
    }

    private void toggleSign() {
        if (expression.isEmpty()) {
            expression = "−";
        } else {
            int start = lastNumberStart();
            String tail = expression.substring(start);
            if (tail.startsWith("−")) expression = expression.substring(0, start) + tail.substring(1);
            else if (!tail.isEmpty() && !endsWithOperator()) expression = expression.substring(0, start) + "−" + tail;
            else if (endsWithOperator()) expression += "−";
        }
        justEvaluated = false;
        show(expression.isEmpty() ? "0" : expression, "");
    }

    private int lastNumberStart() {
        for (int i = expression.length() - 1; i >= 0; i--) {
            char ch = expression.charAt(i);
            if (ch == '+' || ch == '×' || ch == '÷') return i + 1;
            if (ch == '−' && i != 0) return i + 1;
        }
        return 0;
    }

    private boolean endsWithOperator() {
        if (expression.isEmpty()) return false;
        char ch = expression.charAt(expression.length() - 1);
        return ch == '+' || ch == '−' || ch == '×' || ch == '÷';
    }

    private boolean isOperator(String key) {
        return key.equals("+") || key.equals("−") || key.equals("×") || key.equals("÷");
    }

    private void show(String result, String hint) {
        resultView.setText(result);
        expressionView.setText(hint.isEmpty() ? " " : hint);
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    /** Recursive-descent arithmetic parser with normal operator precedence. */
    private static final class Parser {
        private final String input;
        private int position;

        Parser(String expression) {
            input = expression.replace("−", "-").replace("×", "*").replace("÷", "/").replace(" ", "");
        }

        BigDecimal parse() {
            BigDecimal value = expression();
            if (position != input.length()) throw new IllegalArgumentException("Unexpected character");
            return value;
        }

        private BigDecimal expression() {
            BigDecimal value = term();
            while (true) {
                if (take('+')) value = value.add(term());
                else if (take('-')) value = value.subtract(term());
                else return value;
            }
        }

        private BigDecimal term() {
            BigDecimal value = number();
            while (true) {
                if (take('*')) value = value.multiply(number());
                else if (take('/')) value = value.divide(number(), new MathContext(12, RoundingMode.HALF_UP));
                else return value;
            }
        }

        private BigDecimal number() {
            if (take('+')) return number();
            if (take('-')) return number().negate();
            int start = position;
            boolean dot = false;
            while (position < input.length()) {
                char ch = input.charAt(position);
                if (Character.isDigit(ch)) position++;
                else if (ch == '.' && !dot) { dot = true; position++; }
                else break;
            }
            if (start == position || input.substring(start, position).equals(".")) throw new IllegalArgumentException("Number expected");
            return new BigDecimal(input.substring(start, position));
        }

        private boolean take(char expected) {
            if (position < input.length() && input.charAt(position) == expected) {
                position++;
                return true;
            }
            return false;
        }
    }
}
