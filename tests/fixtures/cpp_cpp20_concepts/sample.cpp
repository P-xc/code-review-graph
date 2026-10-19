// C++20 concepts and variable templates must produce nodes.
// Before the fix both were absent from the graph entirely.
#include <cstddef>

template <typename T>
constexpr bool is_int_v = false;

template <>
constexpr bool is_int_v<int> = true;

template <typename T>
concept Integral = is_int_v<T>;

template <Integral T>
T clamp_value(T value, T lo, T hi) {
    return value < lo ? lo : (value > hi ? hi : value);
}

// A member function with a trailing ref-qualifier and a decltype return:
// the shape that a naive "constant" probe mistakes for a variable template.
struct Wrapper {
    int v = 0;
    template <class F>
    constexpr decltype(static_cast<int>(sizeof(F))) map(F&& f) & {
        (void)f;
        return static_cast<int>(sizeof(F));
    }
    int plain_method() const { return v; }
};

int main() {
    Wrapper w{};
    auto c = clamp_value(5, 0, 10);
    return c + w.plain_method();
}
