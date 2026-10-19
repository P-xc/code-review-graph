// C++ type aliases must produce nodes.
// Before the fix, `using X = Y;` contributed nothing to the graph, so the
// 159 calls against int_t in type_safe stayed unresolved.

// namespace-scope alias with a template argument
using int_t = integer<int>;

// alias to a primitive
using flag = bool;

// alias template
template <typename T>
using ptr = T *;

// nested namespace
namespace detail {
using size_type = unsigned long;
} // namespace detail

// member alias inside a class
struct Wrapper {
    using value_type = int;
    value_type get() const { return 1; }
};

// an ordinary function, to prove aliases do not displace anything
int add(int a, int b) { return a + b; }

int main() {
    Wrapper w{};
    ptr<int> p = nullptr;
    (void)p;
    detail::size_type s = 1;
    (void)s;
    return add(w.get(), static_cast<int>(s));
}
