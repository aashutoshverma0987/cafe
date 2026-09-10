// ======================================================
// LUMO CAFE - MAIN JAVASCRIPT
// ======================================================

let cart = [];


// ======================================================
// ADD NORMAL PRODUCT TO CART
// ======================================================

function addToCart(id, name, price) {

    const cartId = id + "-normal";

    const existingItem = cart.find(
        item => item.cartId === cartId
    );

    if (existingItem) {

        existingItem.quantity += 1;

    } else {

        cart.push({
            cartId: cartId,
            id: id,
            name: name,
            size: null,
            price: Number(price),
            quantity: 1
        });

    }

    updateCart();

    openCart();
}


// ======================================================
// ADD PIZZA TO CART
// ======================================================

function addPizzaToCart(id, name, size, price) {

    const cartId = id + "-" + size;

    const existingItem = cart.find(
        item => item.cartId === cartId
    );

    if (existingItem) {

        existingItem.quantity += 1;

    } else {

        cart.push({
            cartId: cartId,
            id: id,
            name: name,
            size: size,
            price: Number(price),
            quantity: 1
        });

    }

    updateCart();

    openCart();
}


// ======================================================
// UPDATE CART
// ======================================================

function updateCart() {

    const cartItems =
        document.getElementById("cartItems");

    const cartCount =
        document.getElementById("cartCount");

    const cartTotal =
        document.getElementById("cartTotal");


    if (!cartItems || !cartCount || !cartTotal) {
        return;
    }


    let totalItems = 0;
    let totalPrice = 0;


    cart.forEach(item => {

        totalItems += item.quantity;

        totalPrice +=
            item.price * item.quantity;

    });


    cartCount.innerText = totalItems;

    cartTotal.innerText =
        "₹" + totalPrice;


    // Empty cart

    if (cart.length === 0) {

        cartItems.innerHTML = `

            <div class="empty-cart">

                <div>🛒</div>

                <p>Your cart is empty</p>

                <span>
                    Add something delicious!
                </span>

            </div>

        `;

        return;
    }


    // Clear cart

    cartItems.innerHTML = "";


    // Create cart items

    cart.forEach(item => {

        const cartItem =
            document.createElement("div");

        cartItem.className = "cart-item";


        const sizeText =
            item.size
                ? `<small>${item.size}</small>`
                : "";


        cartItem.innerHTML = `

            <div class="cart-item-info">

                <h4>
                    ${item.name}
                </h4>

                ${sizeText}

                <span>
                    ₹${item.price}
                </span>

            </div>


            <div class="quantity-controls">

                <button
                    onclick="decreaseQuantity('${item.cartId}')">

                    −

                </button>


                <strong>
                    ${item.quantity}
                </strong>


                <button
                    onclick="increaseQuantity('${item.cartId}')">

                    +

                </button>


                <button
                    class="remove-item"
                    onclick="removeItem('${item.cartId}')">

                    ×

                </button>

            </div>

        `;


        cartItems.appendChild(cartItem);

    });

}


// ======================================================
// INCREASE QUANTITY
// ======================================================

function increaseQuantity(cartId) {

    const item = cart.find(
        item => item.cartId === cartId
    );


    if (item) {

        item.quantity += 1;

    }


    updateCart();
}


// ======================================================
// DECREASE QUANTITY
// ======================================================

function decreaseQuantity(cartId) {

    const item = cart.find(
        item => item.cartId === cartId
    );


    if (!item) {
        return;
    }


    item.quantity -= 1;


    if (item.quantity <= 0) {

        cart = cart.filter(
            item => item.cartId !== cartId
        );

    }


    updateCart();
}


// ======================================================
// REMOVE ITEM
// ======================================================

function removeItem(cartId) {

    cart = cart.filter(
        item => item.cartId !== cartId
    );


    updateCart();
}


// ======================================================
// OPEN CART
// ======================================================

function openCart() {

    const drawer =
        document.getElementById("cartDrawer");

    const overlay =
        document.getElementById("cartOverlay");


    if (drawer) {

        drawer.classList.add("open");

    }


    if (overlay) {

        overlay.classList.add("show");

    }

}


// ======================================================
// CLOSE CART
// ======================================================

function closeCart() {

    const drawer =
        document.getElementById("cartDrawer");

    const overlay =
        document.getElementById("cartOverlay");


    if (drawer) {

        drawer.classList.remove("open");

    }


    if (overlay) {

        overlay.classList.remove("show");

    }

}


// ======================================================
// PIZZA SIZE SELECTION
// ======================================================

function selectSize(button, size, price) {

    const productCard =
        button.closest(".product-card");


    if (!productCard) {
        return;
    }


    // Remove selected from all buttons

    const sizeButtons =
        productCard.querySelectorAll(".size-btn");


    sizeButtons.forEach(btn => {

        btn.classList.remove("selected");

    });


    // Select current button

    button.classList.add("selected");


    // Update price

    const priceElement =
        productCard.querySelector(".pizza-price");


    if (priceElement) {

        priceElement.innerText =
            "₹" + price;

    }


    // Update Add button

    const addButton =
        productCard.querySelector(".add-cart-btn");


    if (addButton) {

        const id =
            Number(productCard.dataset.id);

        const name =
            productCard.querySelector("h3").innerText;


        addButton.onclick = function () {

            addPizzaToCart(
                id,
                name,
                size,
                price
            );

        };

    }

}


// ======================================================
// MENU FILTER
// ======================================================

function filterMenu(category, button) {

    const products =
        document.querySelectorAll(".product-card");


    const buttons =
        document.querySelectorAll(".filter-btn");


    // Remove active

    buttons.forEach(btn => {

        btn.classList.remove("active");

    });


    // Add active

    if (button) {

        button.classList.add("active");

    }


    // Filter products

    products.forEach(product => {

        const productCategory =
            product.dataset.category;


        if (
            category === "All" ||
            productCategory === category
        ) {

            product.style.display = "";

        } else {

            product.style.display = "none";

        }

    });

}


// ======================================================
// VIEW PRODUCT
// ======================================================

function openProduct(id) {

    const product =
        document.querySelector(
            `.product-card[data-id="${id}"]`
        );


    if (!product) {
        return;
    }


    const name =
        product.querySelector("h3").innerText;


    const description =
        product.querySelector(".product-info p")
        ?.innerText || "";


    alert(
        name +
        "\n\n" +
        description
    );

}


// ======================================================
// CHECKOUT
// ======================================================

function checkout() {

    if (cart.length === 0) {

        alert(
            "Your cart is empty. Please add some food first!"
        );

        return;
    }


    alert(
        "Checkout feature will be added in the next step."
    );

}


// ======================================================
// PAGE LOAD
// ======================================================

document.addEventListener(
    "DOMContentLoaded",
    function () {


        // Cart overlay

        const overlay =
            document.getElementById("cartOverlay");


        if (overlay) {

            overlay.addEventListener(
                "click",
                closeCart
            );

        }


        // Checkout button

        const checkoutButton =
            document.querySelector(".checkout-btn");


        if (checkoutButton) {

            checkoutButton.addEventListener(
                "click",
                checkout
            );

        }


        // Login

        const loginButton =
            document.querySelector(".login-btn");


        if (loginButton) {

            loginButton.addEventListener(
                "click",
                function () {

                    alert(
                        "Login feature will be added soon."
                    );

                }
            );

        }


        // Initial cart

        updateCart();


        console.log(
            "LUMO CAFE JavaScript loaded successfully."
        );

    }
);