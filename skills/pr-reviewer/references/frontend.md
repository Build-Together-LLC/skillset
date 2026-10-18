# Frontend Review Rules — React / Vue / React Native

## Table of Contents
1. [React & JSX](#react--jsx)
2. [Vue (Frappe UI / Vue 3)](#vue-frappe-ui--vue-3)
3. [React Native](#react-native)
4. [Frappe Frontend Integration](#frappe-frontend-integration)
5. [State Management](#state-management)
6. [CSS & Styling](#css--styling)
7. [General JavaScript/TypeScript](#general-javascripttypescript)

---

## React & JSX

### 🟠 Major — Hooks Misuse
```jsx
// BAD — missing dependency
useEffect(() => {
  fetchStudents(classId);
}, []); // classId missing from deps — stale closure bug

// GOOD
useEffect(() => {
  fetchStudents(classId);
}, [classId]);

// BAD — creating objects/arrays in render causing infinite re-renders
useEffect(() => {
  doSomething(options);
}, [options]); // if options is defined inline as {}, this runs every render

// BAD — side effect in render body
function StudentList() {
  fetch('/api/students'); // side effect outside useEffect!
  return <div>...</div>;
}
```

Flag these:
- `useEffect` with empty deps `[]` when variables from outer scope are used inside → 🟠
- `useEffect` without cleanup for subscriptions/timers/event listeners → 🟠
- Setting state inside `useEffect` without proper dependency management → 🟠
- `useState` for derived data that should be `useMemo` → 🟡

### 🟠 Major — Component Issues
- Components over 200 lines without splitting into sub-components
- Prop drilling through 3+ levels (consider context or state management)
- Missing `key` prop on list-rendered elements, or using array index as key on dynamic lists
- Direct DOM manipulation (`document.querySelector`, `document.getElementById`) in React
- Using `dangerouslySetInnerHTML` without sanitization → 🔴 Critical (XSS)

### 🟡 Minor — React Style
- Missing PropTypes or TypeScript types for component props
- Default export mixed with named exports inconsistently
- Event handler not using `useCallback` when passed as prop to memoized child
- Inline function definitions in JSX that create new references each render
- Missing error boundaries around components that do data fetching
- Not destructuring props: `function Comp(props)` vs `function Comp({ name, age })`

### 💡 Suggestions
- Complex conditional rendering could use early returns for readability
- Repeated state shape → consider `useReducer` instead of multiple `useState`
- Component could benefit from `React.memo()` if re-rendered frequently with same props

---

## Vue (Frappe UI / Vue 3)

### 🟠 Major
- Mutating props directly instead of emitting events to parent
- Missing `v-if` / `v-show` distinction (using `v-if` for frequent toggles is expensive)
- Watchers on entire objects without `{ deep: true }` when deep watching is needed (or vice versa — deep watching when not needed, causing perf issues)
- `v-for` without `:key` binding
- Mixing Options API and Composition API in the same component without reason
- Using `this.$forceUpdate()` — almost always indicates a reactivity problem

### 🟡 Minor
- Component not using `<script setup>` syntax (v15 Frappe UI standard)
- Missing `defineProps` / `defineEmits` type declarations
- Oversized `<template>` blocks — extract into sub-components
- Not using computed properties for derived state
- `ref()` when `reactive()` is more appropriate (or vice versa)

### Frappe UI Components
- Reinventing components that exist in Frappe UI (Button, Dialog, Input, etc.) → 🟡
- Not using Frappe UI's built-in form controls for standard fields → 🟡
- Custom CSS overriding Frappe UI design tokens without justification → 🟡

---

## React Native

### 🔴 Critical
- Storing sensitive data (tokens, passwords) in `AsyncStorage` without encryption
- Using `eval()` or dynamic code execution

### 🟠 Major — Performance
```jsx
// BAD — ScrollView for long lists
<ScrollView>
  {students.map(s => <StudentCard key={s.id} student={s} />)}
</ScrollView>

// GOOD — FlatList for long/dynamic lists
<FlatList
  data={students}
  renderItem={({ item }) => <StudentCard student={item} />}
  keyExtractor={item => item.id}
/>
```

Flag these:
- Using `ScrollView` for lists with potentially >20 items → 🟠
- Missing `keyExtractor` on FlatList/SectionList → 🟡
- Images without explicit dimensions or without `resizeMode` → 🟠
- Not using `React.memo` on list item components → 🟡
- Inline styles on frequently re-rendered components (create `StyleSheet.create`) → 🟡
- Missing keyboard avoidance (`KeyboardAvoidingView`) on forms → 🟠

### 🟡 Minor — React Native Style
- Platform-specific code without `Platform.OS` checks or platform files (`.ios.js` / `.android.js`)
- Hardcoded pixel values that should use responsive sizing
- Missing `accessible` and `accessibilityLabel` props on interactive elements
- Using `setTimeout` for animations instead of `Animated` API or Reanimated

---

## Frappe Frontend Integration

### 🟠 Major — API Calls
```javascript
// BAD — no error handling on frappe.call
frappe.call({
  method: 'app.api.get_students',
  args: { class: classId }
}).then(r => setStudents(r.message));

// GOOD — with error handling and loading state
frappe.call({
  method: 'app.api.get_students',
  args: { class: classId },
  freeze: true,
  freeze_message: __('Loading students...')
}).then(r => {
  if (r.message) setStudents(r.message);
}).catch(err => {
  frappe.msgprint(__('Failed to load students'));
  console.error(err);
});
```

Flag these:
- `frappe.call` without `.catch()` or error callback → 🟠
- `frappe.xcall` without try/catch in async context → 🟠
- Missing loading/freeze state on user-triggered API calls → 🟡
- Hardcoded API method paths that should reference a constant → 🟡
- Not using `__()` for user-facing strings (translation) → 🟡

### Client Scripts (Frappe Form Scripts)
- `cur_frm` usage in new code — prefer `frm` parameter from event handlers → 🟡
- Client script modifying server-side fields without validation → 🟠
- Missing `frm.dirty()` check before making server calls → 🟡
- Heavy logic in `refresh` event that should be in `onload` or triggered event → 🟡
- Not using `frappe.ui.form.on` properly (missing doctype parameter) → 🟠

---

## State Management

### 🟠 Major
- Global mutable state outside of state management solution
- State stored in module-level variables that persist between renders/navigations
- Async state not handling race conditions (component unmounted before response)
- Missing cleanup: component fetches data but doesn't cancel on unmount

### 🟡 Minor
- State that belongs in URL/query params stored in component state
- Form state not reset on route change
- Derived state stored separately instead of computed from source state

---

## CSS & Styling

### 🟠 Major
- `!important` used more than once in the same file → code smell
- Inline styles with dynamic values that could be CSS variables
- Z-index wars (values like `z-index: 99999`)
- Fixed pixel widths breaking responsive layouts

### 🟡 Minor
- Color values not using CSS variables / design tokens
- Duplicate style rules across components
- Magic numbers in margins/paddings without comment
- Missing responsive breakpoints on layout components

---

## General JavaScript/TypeScript

### 🔴 Critical
- `eval()`, `new Function()`, or `innerHTML` with user input → XSS
- Credentials or tokens in frontend code

### 🟠 Major
- `var` instead of `const`/`let` → 🟡 (upgrade to 🟠 if it causes scoping bugs)
- `==` instead of `===` without intentional type coercion
- Unhandled promise rejections (missing `.catch()` or try/catch on await)
- Modifying function parameters (objects/arrays) instead of creating copies
- `async` function without any `await` inside

### 🟡 Minor
- `console.log` left in production code
- Nested ternaries that hurt readability
- Arrow functions without parentheses on single param inconsistently
- Not using optional chaining (`?.`) where null checks are verbose
- String concatenation instead of template literals
- Unused variables or imports (should be caught by linter, but flag if present)

### TypeScript-Specific
- Using `any` type without justification → 🟡
- Missing return type annotations on exported functions → 🟡
- Type assertions (`as Type`) hiding actual type mismatches → 🟠
- Not using interface/type for API response shapes → 🟡
