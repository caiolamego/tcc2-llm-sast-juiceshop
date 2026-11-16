// ruleid: tcc.validation.security.rating-without-range
Review.init({ rating: { type: DataTypes.INTEGER, allowNull: false } }, { sequelize });
// ok: tcc.validation.security.rating-without-range
Review.init({ rating: { type: DataTypes.INTEGER, validate: { min: 1, max: 5 } } }, { sequelize });
// Falso positivo conhecido: validacao em middleware nao visivel nesta regra.
installRatingValidation();
// ruleid: tcc.validation.security.rating-without-range
Feedback.init({ rating: { type: DataTypes.INTEGER } }, { sequelize });
