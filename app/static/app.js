const productsEl = document.querySelector('#products');

function formatPrice(priceCents, currency) {
  return new Intl.NumberFormat('ja-JP', {
    style: 'currency',
    currency: currency.toUpperCase(),
  }).format(priceCents / 100);
}

async function loadProducts() {
  productsEl.innerHTML = '<p>商品を読み込んでいます...</p>';
  const response = await fetch('/api/products');
  const products = await response.json();
  productsEl.innerHTML = '';

  products.forEach((product) => {
    const card = document.createElement('article');
    card.className = 'card';
    card.innerHTML = `
      <h2>${product.name}</h2>
      <p>${product.description}</p>
      <p class="price">${formatPrice(product.price_cents, product.currency)}</p>
      <form data-product-id="${product.id}">
        <label>
          メールアドレス
          <input name="email" type="email" placeholder="you@example.com" required />
        </label>
        <button type="submit">購入する</button>
      </form>
      <p class="message" role="status"></p>
    `;
    productsEl.appendChild(card);
  });
}

productsEl.addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.target;
  const message = form.parentElement.querySelector('.message');
  const button = form.querySelector('button');
  button.disabled = true;
  message.textContent = '決済URLを作成しています...';

  try {
    const response = await fetch('/api/checkout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        product_id: form.dataset.productId,
        customer_email: form.email.value,
      }),
    });
    if (!response.ok) {
      throw new Error('Checkout failed');
    }
    const checkout = await response.json();
    window.location.href = checkout.checkout_url;
  } catch (error) {
    message.textContent = '決済URLを作成できませんでした。';
    button.disabled = false;
  }
});

loadProducts();
