// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title WrapSell
 * @dev ERC20 token backed by multiple units of a specific TCG card as collateral
 */
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
    uint256 public estimatedValuePerCard; // Value per individual card unit

    // Owner and permissions
    address public owner;
    address public wrapPool; // The WrapPool that manages this contract

    // Balances and allowances
    mapping(address => uint256) private _balances;
    mapping(address => mapping(address => uint256)) private _allowances;

    // Card collateral tracking
    mapping(address => uint256) public cardDeposits; // User => number of cards deposited
    uint256 public totalCardsDeposited;
    uint256 public totalTokensIssued;

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
    event CardInfoUpdated(
        string cardName,
        string rarity,
        uint256 estimatedValue
    );

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
        uint256 _estimatedValuePerCard
    ) {
        name = _name;
        symbol = _symbol;
        cardId = _cardId;
        cardName = _cardName;
        rarity = _rarity;
        estimatedValuePerCard = _estimatedValuePerCard;
        owner = msg.sender;
        wrapPool = msg.sender; // Initially set to deployer, can be updated
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
        string memory _rarity,
        uint256 _estimatedValuePerCard
    ) external onlyOwner {
        cardName = _cardName;
        rarity = _rarity;
        estimatedValuePerCard = _estimatedValuePerCard;
        emit CardInfoUpdated(_cardName, _rarity, _estimatedValuePerCard);
    }

    /**
     * @dev Deposit cards as collateral and receive tokens
     * @param cardCount Number of cards to deposit
     */
    function depositCards(uint256 cardCount) external payable {
        require(cardCount > 0, "Must deposit at least 1 card");

        // For demo purposes, we're using ETH as proxy for card value
        // In production, this would verify actual card ownership/custody
        uint256 requiredValue = cardCount * estimatedValuePerCard;
        require(msg.value >= requiredValue, "Insufficient payment for cards");

        // Issue tokens 1:1 with card value
        uint256 tokensToIssue = cardCount * estimatedValuePerCard;

        cardDeposits[msg.sender] += cardCount;
        totalCardsDeposited += cardCount;
        totalTokensIssued += tokensToIssue;

        // Mint tokens
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

        uint256 tokensToBurn = cardCount * estimatedValuePerCard;
        require(
            _balances[msg.sender] >= tokensToBurn,
            "Insufficient token balance"
        );

        // Burn tokens
        totalSupply -= tokensToBurn;
        _balances[msg.sender] -= tokensToBurn;

        // Update deposits
        cardDeposits[msg.sender] -= cardCount;
        totalCardsDeposited -= cardCount;
        totalTokensIssued -= tokensToBurn;

        // Transfer value back to user
        uint256 valueToReturn = cardCount * estimatedValuePerCard;
        payable(msg.sender).transfer(valueToReturn);

        emit Transfer(msg.sender, address(0), tokensToBurn);
        emit CardsWithdrawn(msg.sender, cardCount, tokensToBurn);
    }

    /**
     * @dev Get total collateral value (needed by WrapPool)
     */
    function getTotalCollateralValue() external view returns (uint256) {
        return totalCardsDeposited * estimatedValuePerCard;
    }

    /**
     * @dev Get collateral information
     */
    function getCollateralInfo()
        external
        view
        returns (
            uint256 totalCards,
            uint256 totalValue,
            uint256 tokensIssued,
            uint256 collateralizationRatio
        )
    {
        totalCards = totalCardsDeposited;
        totalValue = totalCardsDeposited * estimatedValuePerCard;
        tokensIssued = totalTokensIssued;

        if (totalTokensIssued > 0) {
            collateralizationRatio = (totalValue * 100) / totalTokensIssued;
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
            uint256 cardsDeposited,
            uint256 tokenBalance,
            uint256 userCollateralValue
        )
    {
        cardsDeposited = cardDeposits[user];
        tokenBalance = _balances[user];
        userCollateralValue = cardsDeposited * estimatedValuePerCard;
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
            string memory _rarity,
            uint256 _estimatedValuePerCard
        )
    {
        return (cardId, cardName, rarity, estimatedValuePerCard);
    }
}
