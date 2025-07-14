/**
 * @title WrapSell (Chainlink-enabled)
 * @dev ERC20 token backed by multiple units of a specific TCG card as collateral, using Chainlink price feeds for dynamic card valuation.
 */
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// Chainlink AggregatorV3Interface for price feeds
interface AggregatorV3Interface {
    function decimals() external view returns (uint8);

    function description() external view returns (string memory);

    function version() external view returns (uint256);

    function getRoundData(
        uint80 _roundId
    )
        external
        view
        returns (
            uint80 roundId,
            int256 answer,
            uint256 startedAt,
            uint256 updatedAt,
            uint80 answeredInRound
        );

    function latestRoundData()
        external
        view
        returns (
            uint80 roundId,
            int256 answer,
            uint256 startedAt,
            uint256 updatedAt,
            uint80 answeredInRound
        );
}

contract WrapSell {
    // ERC20 Basic Variables
    string public name;
    string public symbol;
    uint8 public constant decimals = 18;
    uint256 public totalSupply;

    // Card information
    uint256 public cardId;
    string public cardName;
    string public rarity;

    // Owner and permissions
    address public owner;
    address public wrapPool;

    // Balances and allowances
    mapping(address => uint256) private _balances;
    mapping(address => mapping(address => uint256)) private _allowances;

    // Card collateral tracking
    mapping(address => uint256) public cardDeposits;
    uint256 public totalCardsDeposited;
    uint256 public totalTokensIssued;

    // Chainlink price feed
    AggregatorV3Interface public priceFeed; // e.g., ETH/USD

    // Events
    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(
        address indexed owner,
        address indexed spender,
        uint256 value
    );
    event CardsDeposited(
        address indexed user,
        uint256 cardCount,
        uint256 tokensIssued
    );
    event CardsWithdrawn(
        address indexed user,
        uint256 cardCount,
        uint256 tokensBurned
    );
    event CardInfoUpdated(string cardName, string rarity);

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner can call this function");
        _;
    }

    modifier onlyWrapPool() {
        require(msg.sender == wrapPool, "Only WrapPool can call this function");
        _;
    }

    constructor(
        string memory _name,
        string memory _symbol,
        uint256 _cardId,
        string memory _cardName,
        string memory _rarity,
        address _priceFeed
    ) {
        name = _name;
        symbol = _symbol;
        cardId = _cardId;
        cardName = _cardName;
        rarity = _rarity;
        owner = msg.sender;
        wrapPool = msg.sender;
        priceFeed = AggregatorV3Interface(_priceFeed);
        totalCardsDeposited = 0;
        totalTokensIssued = 0;
    }

    /**
     * @dev Set the WrapPool that manages this contract
     */
    function setWrapPool(address _wrapPool) external onlyOwner {
        require(_wrapPool != address(0), "Invalid WrapPool address");
        wrapPool = _wrapPool;
    }

    /**
     * @dev Update card information
     */
    function updateCardInfo(
        string memory _cardName,
        string memory _rarity
    ) external onlyOwner {
        cardName = _cardName;
        rarity = _rarity;
        emit CardInfoUpdated(_cardName, _rarity);
    }

    /**
     * @dev Get latest price from Chainlink price feed (returns price in USD with 8 decimals)
     */
    function getLatestPrice() public view returns (uint256) {
        (, int256 price, , , ) = priceFeed.latestRoundData();
        require(price > 0, "Invalid price");
        return uint256(price);
    }

    /**
     * @dev Deposit cards as collateral and receive tokens
     * @param cardCount Number of cards to deposit
     */
    function depositCards(uint256 cardCount) external payable {
        require(cardCount > 0, "Must deposit at least 1 card");
        uint256 cardUsdPrice = getLatestPrice(); // 8 decimals
        // For demo: 1 token = 1 USD worth of ETH per card
        uint256 requiredUsd = cardCount * cardUsdPrice;
        // Convert USD to ETH (msg.value is in wei, priceFeed is ETH/USD with 8 decimals)
        // ETH amount = requiredUsd * 1e18 / ethUsdPrice
        uint256 ethUsdPrice = getLatestPrice();
        uint256 requiredEth = (requiredUsd * 1e18) / ethUsdPrice;
        require(msg.value >= requiredEth, "Insufficient ETH sent");

        // Issue tokens 1:1 with USD value (scaled to 18 decimals)
        uint256 tokensToIssue = cardCount * cardUsdPrice * 1e10; // scale to 18 decimals

        cardDeposits[msg.sender] += cardCount;
        totalCardsDeposited += cardCount;
        totalTokensIssued += tokensToIssue;

        totalSupply += tokensToIssue;
        _balances[msg.sender] += tokensToIssue;

        emit Transfer(address(0), msg.sender, tokensToIssue);
        emit CardsDeposited(msg.sender, cardCount, tokensToIssue);
    }

    /**
     * @dev Withdraw cards by burning tokens
     * @param cardCount Number of cards to withdraw
     */
    function withdrawCards(uint256 cardCount) external {
        require(cardCount > 0, "Must withdraw at least 1 card");
        require(
            cardDeposits[msg.sender] >= cardCount,
            "Insufficient card deposits"
        );

        uint256 cardUsdPrice = getLatestPrice();
        uint256 tokensToBurn = cardCount * cardUsdPrice * 1e10; // scale to 18 decimals
        require(
            _balances[msg.sender] >= tokensToBurn,
            "Insufficient token balance"
        );

        totalSupply -= tokensToBurn;
        _balances[msg.sender] -= tokensToBurn;

        cardDeposits[msg.sender] -= cardCount;
        totalCardsDeposited -= cardCount;
        totalTokensIssued -= tokensToBurn;

        // Return ETH equivalent to user
        uint256 ethUsdPrice = getLatestPrice();
        uint256 usdToReturn = cardCount * cardUsdPrice;
        uint256 ethToReturn = (usdToReturn * 1e18) / ethUsdPrice;
        payable(msg.sender).transfer(ethToReturn);

        emit Transfer(msg.sender, address(0), tokensToBurn);
        emit CardsWithdrawn(msg.sender, cardCount, tokensToBurn);
    }

    /**
     * @dev Get total collateral value in USD (using Chainlink)
     */
    function getTotalCollateralValue() external view returns (uint256) {
        uint256 cardUsdPrice = getLatestPrice();
        return totalCardsDeposited * cardUsdPrice;
    }

    /**
     * @dev Get collateral information
     */
    function getCollateralInfo()
        external
        view
        returns (
            uint256 totalCards,
            uint256 totalValueUsd,
            uint256 tokensIssued,
            uint256 collateralizationRatio
        )
    {
        uint256 cardUsdPrice = getLatestPrice();
        totalCards = totalCardsDeposited;
        totalValueUsd = totalCardsDeposited * cardUsdPrice;
        tokensIssued = totalTokensIssued;

        if (totalTokensIssued > 0) {
            collateralizationRatio = (totalValueUsd * 100) / totalTokensIssued;
        } else {
            collateralizationRatio = 0;
        }
    }

    /**
     * @dev Get user's card deposit information
     */
    function getUserCardInfo(
        address user
    )
        external
        view
        returns (
            uint256 cardsDeposited_,
            uint256 tokenBalance,
            uint256 userCollateralValueUsd
        )
    {
        uint256 cardUsdPrice = getLatestPrice();
        cardsDeposited_ = cardDeposits[user];
        tokenBalance = _balances[user];
        userCollateralValueUsd = cardsDeposited_ * cardUsdPrice;
    }

    // --- ERC20 Functions ---

    function balanceOf(address account) public view returns (uint256) {
        return _balances[account];
    }

    function transfer(address to, uint256 amount) public returns (bool) {
        _transfer(msg.sender, to, amount);
        return true;
    }

    function approve(address spender, uint256 amount) public returns (bool) {
        _approve(msg.sender, spender, amount);
        return true;
    }

    function allowance(
        address owner_,
        address spender
    ) public view returns (uint256) {
        return _allowances[owner_][spender];
    }

    function transferFrom(
        address from,
        address to,
        uint256 amount
    ) public returns (bool) {
        uint256 currentAllowance = _allowances[from][msg.sender];
        require(
            currentAllowance >= amount,
            "ERC20: transfer amount exceeds allowance"
        );

        _transfer(from, to, amount);
        _approve(from, msg.sender, currentAllowance - amount);

        return true;
    }

    // --- Internal Functions ---

    function _transfer(address from, address to, uint256 amount) internal {
        require(from != address(0), "ERC20: transfer from the zero address");
        require(to != address(0), "ERC20: transfer to the zero address");
        require(
            _balances[from] >= amount,
            "ERC20: transfer amount exceeds balance"
        );

        _balances[from] -= amount;
        _balances[to] += amount;

        emit Transfer(from, to, amount);
    }

    function _approve(
        address owner_,
        address spender,
        uint256 amount
    ) internal {
        require(owner_ != address(0), "ERC20: approve from the zero address");
        require(spender != address(0), "ERC20: approve to the zero address");

        _allowances[owner_][spender] = amount;
        emit Approval(owner_, spender, amount);
    }

    // --- Admin Functions ---

    function emergencyWithdraw(uint256 amount) external onlyOwner {
        require(
            amount <= address(this).balance,
            "Insufficient contract balance"
        );
        payable(owner).transfer(amount);
    }

    // --- View Functions ---

    function getContractBalance() external view returns (uint256) {
        return address(this).balance;
    }

    function getCardInfo()
        external
        view
        returns (
            uint256 _cardId,
            string memory _cardName,
            string memory _rarity
        )
    {
        return (cardId, cardName, rarity);
    }
}
